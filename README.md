# Phone-Use

## Overview
This project utilizes Python and Android Debug Bridge (ADB) to interface with Android devices.

## Prerequisites
- Python 3.11 
- Android Debug Bridge (ADB)
- USB debugging enabled on your Android device
- OmniParser

## Installation

### 1. Clone the repository
```
git clone https://github.com/Jayanth-Adhitya/Phone-use.git
cd Phone-use
```

### 2. Install Python dependencies
```
pip install -r requirements.txt
```

### 3. Install Android Debug Bridge (ADB)

#### Windows
1. Download the Android SDK Platform Tools from [developer.android.com](https://developer.android.com/studio/releases/platform-tools)
2. Extract the ZIP file to a location on your computer
3. Add the platform-tools directory to your system PATH

#### macOS
```
brew install android-platform-tools
```

#### Linux
```
sudo apt-get install android-tools-adb
```

## Instructions for OmniParser
### 1. Download OmniParser
```
git clone https://github.com/microsoft/OmniParser.git
cd OmniParser
```

### 2. Run the Gradio demo
```
python gradio_demo.py
```

## Usage

1. Connect your Android device to your computer via USB
2. Enable USB debugging on your device (Settings > Developer options > USB debugging)
3. Run the script:
```
python main.py
```


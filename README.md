# ha_sagemcom_router

![Home Assistant](https://img.shields.io/badge/Home_Assistant-Custom_Component-blue?logo=home-assistant)

This is a custom Home Assistant integration completely reverse-engineered to monitor the **Sagemcom F@st 5866T 5G Modem** (specifically tailored to the TPG firmware variant). 

Because TPG utilizes a highly customized and nested UNIX SHA-512 cryptographic handshake, standard open-source Sagemcom API libraries fail to authenticate with this model. This integration uses a pure, dependency-free Python hashing engine to flawlessly mimic the modem's native AngularJS frontend. 

It actively polls 24+ live telemetry sensors, including:
* 5G and 4G fallback telemetry (RSRP, RSRQ, SINR, Band)
* Live Wi-Fi 2.4GHz and 5GHz traffic metrics
* Live Ethernet LAN port link speeds
* Cellular session duration and data usage
* Hardware system information and uptime

## Installation

### Method 1: HACS (Recommended)
1. Open **HACS** in your Home Assistant instance.
2. Click the three dots (menu) in the top right corner and select **Custom repositories**.
3. Paste this repository URL into the text box: `https://github.com/Michael-O-Power/ha_sagemcom_router`
4. Set the Category to **Integration**.
5. Click **Add**.
6. Once added, close the menu, search for **Sagemcom** in HACS, click the new integration, and select **Download**.
7. **Restart Home Assistant**.

### Method 2: Manual (Command Line)
If you prefer to install without HACS, you can do it via terminal/SSH.
1. Access your Home Assistant command line.
2. Navigate to your Home Assistant configuration directory (the folder where your `configuration.yaml` is located).
3. If you don't already have a `custom_components` folder, create one:
   ```bash
   mkdir custom_components
   cd custom_components
   ```
4. Clone this repository:
   ```bash
   git clone [https://github.com/Michael-O-Power/ha_sagemcom_router.git](https://github.com/Michael-O-Power/ha_sagemcom_router.git)
   ```
5. Move the internal `sagemcom_router` folder directly into `custom_components`. Your final folder structure should look exactly like this:
   `config/custom_components/sagemcom_router/`
6. **Restart Home Assistant**.

## Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **Sagemcom F@st 5866T**.
4. Enter the following details:
   * **Host:** The IP address of your modem (usually `192.168.1.1`)
   * **Username:** The login username (usually `admin`)
   * **Password:** The exact password used to log into the modem's web interface. *(Note: If you use a password manager to log in via your browser, ensure you copy the exact string it is auto-filling).*
5. Click **Submit**.

Once authenticated, your sensors will begin pulling data within 60 seconds!

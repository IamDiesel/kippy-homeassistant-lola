# Kippy for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

Integrate [Kippy](https://www.kippy.eu/) pet trackers with Home Assistant. Track your pet's location, monitor activity and battery levels, and control tracker features directly from your smart home dashboard.

> ⚠️ **Disclaimer: Unofficial Integration**
> This is an unofficial, community-driven, open-source project. It is **not** affiliated with, endorsed by, sponsored by, or connected to Kippy srl in any way. "Kippy" and any related trademarks are the property of their respective owners. This integration uses an undocumented API, which means it could break or change at any time. Use this software at your own risk.

> **Credits & Acknowledgments**
> This project originally started as a fork of the great work done by [ThomasHFWright/kippy-homeassistant](https://github.com/ThomasHFWright/kippy-homeassistant). However, as the Kippy backend infrastructure evolved, this repository diverged significantly into a standalone project. It features a completely rewritten, robust GraphQL API client and has been heavily refactored to comply with modern, strict Home Assistant architectural guidelines (e.g., removing user-configurable polling, implementing `runtime_data`, and enforcing strict entity naming). Huge thanks to Thomas for providing the initial spark and foundation!

**Please note:** This is a hobby project. It was specifically written and tested for the **Kippy Cat** tracker to keep an eye on our cat Lola. It will likely work with Kippy Evo and Kippy Dog, but since I don't own these devices, I cannot test them.

## Features

1. Creates a `device_tracker` per Kippy in your account.
2. Retrieves location updates with different, dynamically managed rates for idle and live tracking.
3. Enable/disable live tracking.
4. Enable/disable energy saving mode.
5. Fetch daily activity stats (steps, sleep, calories, etc.).
6. **New:** Download historical GPS routes for specific days as a `.geojson` file directly to your Home Assistant `www/` folder (perfect for custom map cards).
7. **New:** Fully compliant with strict Home Assistant architecture guidelines (backend polling is handled programmatically, not via user config).

## Installation

### Via [HACS](https://hacs.xyz/) (Recommended)

1. Open HACS in your Home Assistant instance.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Add `https://github.com/IamDiesel/kippy-homeassistant-lola` and select **Integration** as the category.
4. Search for "Kippy" in HACS, download the integration, and restart Home Assistant.

### Manually

Copy the `custom_components/kippy` folder from this repository into your Home Assistant `config/custom_components` directory and restart Home Assistant.

## Configuration

1. Go to **Settings -> Devices & Services** in Home Assistant.
2. Click **Add Integration** and search for **Kippy**.
3. Sign in with your Kippy credentials. The integration will automatically discover and import your trackers.

## Usage & UI

All controls and sensors are automatically grouped under the Kippy device in Home Assistant.
To export a historical route, simply select the start and end date using the provided calendar controls in the "Diagnostics" section of the device and press the "Download History Route" button. The resulting `kippy_history_<id>.geojson` file can be visualized using custom Lovelace cards like the `ha-map-card`.

## Contributing

Contributions are very welcome! Since this is a hobby project, any help in maintaining the code, adding features, or ensuring compatibility with Kippy Evo/Dog is greatly appreciated.

Please open an issue or pull request if you want to contribute. Running `python script/hassfest --integration-path custom_components/kippy` and checking against `flake8` / `black` locally before submitting helps keep the project healthy.

---

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[license-shield]: https://img.shields.io/github/license/IamDiesel/kippy-homeassistant-lola.svg
[releases-shield]: https://img.shields.io/github/v/release/IamDiesel/kippy-homeassistant-lola.svg
[releases]: https://github.com/IamDiesel/kippy-homeassistant-lola/releases

<div align="center">

# 🚀 Parch Driver Manager

A modern, fast, and intuitive driver manager for Parch Linux and other Arch-based distributions, built with **Python**, **GTK4**, and **Libadwaita**.

![GTK4](https://img.shields.io/badge/GTK4-3D3D3D?style=for-the-badge&logo=gtk&logoColor=white)
![Libadwaita](https://img.shields.io/badge/Libadwaita-3584E4?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

---

## ✨ Features

- **🖥️ Automatic Hardware Detection:** Scans `lspci` to detect GPUs, Network cards, Audio devices, and Bluetooth controllers automatically.
- **📦 Driver Management:** Install and remove driver profiles seamlessly using `pacman` with `pkexec` for secure privilege escalation.
- **⚙️ Hardware Control:** Enable or disable specific hardware modules on the fly using `modprobe` and kernel blacklisting.
- **🎨 Modern UI:** Built entirely with GTK4 and Libadwaita, featuring a responsive split-view design, smooth transitions, and standard window controls.
- **📋 Operation Logging:** Real-time background logging for all operations (installs, removals, errors) to help with troubleshooting.
- **🕵️ System Info:** Displays crucial system information like Session Type (X11/Wayland), Hybrid GPU status, and Secure Boot state.

---

## 📋 Prerequisites

Before running Parch Driver Manager, ensure you have the following system dependencies installed:

- **Python 3** (>= 3.9)
- **GTK4** & **Libadwaita**
- **Polkit** (for `pkexec` privilege escalation)
- `pacman` (Arch Linux package manager)
- `lspci` (usually part of `pciutils`)

---

## 🛠️ Installation

### 1. Install System Dependencies

On Parch Linux, run:

```bash
sudo pacman -S gtk4 libadwaita python-gobject pciutils polkit
```

### 2. Clone the Repository

```bash
git clone [https://github.com/your-username/parch-driver-manager.git](https://github.com/parchlinux/Parch-Driver-Manager/)
cd Parch-driver-manager
```

### 3. Install Python Dependencies

It is recommended to use a virtual environment, but you can install it globally as well:

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

Run the application using the main entry point:

```bash
python main.py
```

*Note: Since the application uses `pkexec` for package management and module loading, you will be prompted for your administrator password when performing system-altering actions.*

---

## 📂 Project Structure

The project follows a modular architecture to separate concerns between logic, data, and UI:

```text
.
├── main.py              # Entry point of the application
├── ui.py                # GTK4/Libadwaita UI components and windows
├── manager.py           # Core logic for installing, removing, and toggling drivers
├── profiles.py          # Driver profile definitions (GPU, Network, Audio, Bluetooth)
├── backend.py           # Privileged command execution (pkexec wrapper)
├── system_prober.py     # Hardware detection and system information fetching
└── requirements.txt     # Python dependencies (PyGObject)
```

---

## 📦 How It Works

1. **System Prober:** Reads `lspci -nnk` and environment variables to detect hardware and active kernel modules.
2. **Profiles:** Maps detected hardware (like an NVIDIA GPU) to a set of required packages (e.g., `nvidia-dkms`, `nvidia-utils`).
3. **Backend Runner:** Constructs commands and executes them with `pkexec` to ensure the user has the necessary root permissions.
4. **Driver Manager:** Orchestrates the operations between the UI, profiles, and backend, handling progress updates and error catching.

---

## 📜 License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

<div align="center">
  Made with ❤️ for Parch Linux
</div>

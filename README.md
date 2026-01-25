# Introduction

This is my kanata configuration. The main file is `.config/kanata/kanata.kbd`.
To run kanata with my configuration as a service, you can find the file in
`.config/systemd/user/kanata.service`.

You can use `stow` to set the configuration by running in the root of this
project:

```bash
stow -t ~ -v .
```

To install the service:

```bash
systemctl --user daemon-reload
systemctl --user enable kanata.service
systemctl --user start kanata.service
```

To check if the service is running:

```bash
systemctl --user status kanata.service
```

To view log:

```bash
journalctl --user -u kanata -f -n 100
```

To reload kanata configuration use `Tab+r`.

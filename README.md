# utun

A small tool for tunneling UDP over TCP.

This tool can be used to securely publish applications that use UDP, such as game servers like Palworld, through SSH tunnels or similar methods.

You can use this tool to publish services through a VPS server without exposing your home IP address.

## How It Works

![image](image.png)

`utun-frontend` converts UDP communication from the client to TCP, while `utun-backend` converts the TCP communication back to UDP.
Because `utun-frontend` and `utun-backend` communicate over TCP, their connection can be routed through an SSH tunnel or similar methods.

## Requirements

* Python 3

## Installation

```sh
pip install git+https://github.com/ttk1/utun.git
```

## Usage

TODO

## Example

TODO

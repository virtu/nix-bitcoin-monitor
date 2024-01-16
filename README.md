# nix-bitcoin-monitor
A monitoring framework for Bitcoin Core

## Manual runs

```bash
nix run . -- \
  --rpc-user privileged \
  --rpc-password $(sudo cat /etc/nix-bitcoin-secrets/bitcoin-rpcpassword-privileged)
```

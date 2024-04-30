# nix-bitcoin-monitor

A monitoring framework for Bitcoin Core

## Manual runs

```bash
nix run . -- \
  --rpc-user privileged \
  --rpc-password $(sudo cat /etc/nix-bitcoin-secrets/bitcoin-rpcpassword-privileged)
```

## To-do list

- [ ] Improve persisting results
  - [ ] Use dedicated class
  - [ ] Store results in `--result-path` directory
  - [ ] Use dedicated file for each day
  - [ ] Compress daily files and backup to GCS
- [ ] Support additional RPC calls
- [ ] Add support for debug log
- [ ] Add support for eBPF interface
- [ ] Add support for zmq interface

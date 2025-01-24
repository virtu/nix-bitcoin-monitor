flake: { config, pkgs, lib, ... }:

with lib;

let
  inherit (flake.packages.${pkgs.stdenv.hostPlatform.system}) nix-bitcoin-monitor;
  cfg = config.services.nix-bitcoin-monitor;
in
{
  options = {
    services.nix-bitcoin-monitor = {
      enable = mkEnableOption "nix-bitcoin-monitor";

      logLevel = mkOption {
        type = types.str;
        default = "INFO";
        example = "DEBUG";
        description = mdDoc "Log verbosity for console.";
      };

      resultPath = mkOption {
        type = types.path;
        default = "/home/nix-bitcoin-monitor/";
        example = "/scratch/results/nix-bitcoin-monitor";
        description = mdDoc "Directory for results.";
      };

      bitcoinRpcHost = mkOption {
        type = types.str;
        default = "127.0.0.1";
        example = "192.168.1.100";
        description = mdDoc "Host for Bitcoin's RPC API.";
      };

      bitcoinRpcPort = mkOption {
        type = types.port;
        default = 8332;
        example = 1234;
        description = mdDoc "Port for Bitcoin's RPC API.";
      };

      bitcoinRpcUser = mkOption {
        type = types.str;
        default = "privileged";
        example = "username";
        description = mdDoc "Username for Bitcoin's RPC API.";
      };

      bitcoinRpcPass = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "passw0rd";
        description = mdDoc "Password for Bitcoin's RPC API.";
      };

      bitcoinRpcPassFile = mkOption {
        type = types.nullOr types.path;
        default = "/etc/nix-bitcoin-secrets/bitcoin-rpcpassword-privileged";
        example = "path/to/password.txt";
        description = mdDoc "File containing password for Bitcoin's RPC API.";
      };

      sources = {
        rpcGetconnectioncount = mkEnableOption "collecting getconnectioncount data (RPC)" // { default = true; };
        rpcGetpeerinfo = mkEnableOption "collecting getpeerinfo data (RPC)" // { default = true; };
        rpcGettxoutsetinfo = mkEnableOption "collecting gettxoutsetinfo data (RPC)" // { default = true; };
        rpcGetnodeaddresses = mkEnableOption "collecting getnodeaddresses data (RPC)" // { default = true; };
        rpcGetrawaddrman = mkEnableOption "collecting getrawaddrman data (RPC)" // { default = true; };
        tracepointsNet = mkEnableOption "collecting net group data (tracepoints)" // { default = true; };
        systemdIPAccounting = mkEnableOption "collecting IP accounting statistics (systemd)" // { default = true; };
        iptablesP2PTraffic = mkEnableOption "collecting Bitcoin Core P2P traffic (iptables)" // { default = true; };
      };
    };
  };

  config = mkIf cfg.enable {

    users = {
      users.nix-bitcoin-monitor = {
        isSystemUser = true;
        group = "nix-bitcoin-monitor";
        home = "/home/nix-bitcoin-monitor";
        createHome = true;
        homeMode = "755";
        extraGroups = [ "bitcoin" ]; # so user can access secrets generated by nix-bitcoin
      };
      groups.nix-bitcoin-monitor = { };
    };

    # if Bitcoin Core P2P traffic measurement via iptables is enabled, add appropriate iptables rules
    networking.firewall.extraCommands = lib.mkIf cfg.sources.iptablesP2PTraffic ''
      iptables -I INPUT -p tcp --dport 8333 -j ACCEPT -m comment --comment "bitcoind_p2p_in"
      iptables -I OUTPUT -p tcp --sport 8333 -j ACCEPT -m comment --comment "bitcoind_p2p_out"
    '';

    systemd.services.nix-bitcoin-monitor = {
      description = "Monitoring infrastructure for Bitcoin Core";
      wantedBy = [ "multi-user.target" ];
      requires = [ "bitcoind.service" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" "bitcoind.service" ];
      serviceConfig = {
        # for now, run as root to avoid permission issues with eBPF/tracepoints
        # at some point, figure out how to address this properly (e.g.,
        # user-specific eBPF permissions or a SET_CAP binary accessible only by
        # the user)
        User = "root";
        PrivateTmp = "yes";
        ExecStartPre = ''${pkgs.coreutils}/bin/sleep 60''; # wait for bitcoind to be ready to serve API calls
        ExecStart = ''${nix-bitcoin-monitor}/bin/bitcoin-monitor \
          --log-level=${cfg.logLevel} \
          --result-path=${cfg.resultPath} \
          --rpc-host=${cfg.bitcoinRpcHost} \
          --rpc-port=${toString cfg.bitcoinRpcPort} \
          --rpc-user=${cfg.bitcoinRpcUser} \
          ${optionalString (cfg.bitcoinRpcPass != null) "--rpc-password=${cfg.bitcoinRpcPass}" } \
          ${optionalString (cfg.bitcoinRpcPassFile != null) "--rpc-password-file=${cfg.bitcoinRpcPassFile}" } \
          ${if cfg.sources.rpcGetconnectioncount then "--record-rpc-getconnectioncount" else "--no-record-rpc-getconnectioncount"} \
          ${if cfg.sources.rpcGetpeerinfo then "--record-rpc-getpeerinfo" else "--no-record-rpc-getpeerinfo"} \
          ${if cfg.sources.rpcGettxoutsetinfo then "--record-rpc-gettxoutsetinfo" else "--no-record-rpc-gettxoutsetinfo"} \
          ${if cfg.sources.rpcGetnodeaddresses then "--record-rpc-getnodeaddresses" else "--no-record-rpc-getnodeaddresses"} \
          ${if cfg.sources.rpcGetrawaddrman then "--record-rpc-getrawaddrman" else "--no-record-rpc-getrawaddrman"} \
          ${if cfg.sources.tracepointsNet then "--record-tracepoints-net" else "--no-record-tracepoints-net"} \
          ${if cfg.sources.systemdIPAccounting then "--record-systemd-ip-accounting" else "--no-record-systemd-ip-accounting"} \
          ${if cfg.sources.iptablesP2PTraffic then "--record-iptables-p2p-traffic" else "--no-record-iptables-p2p-traffic"} \
        '';
        Restart = "on-failure";
        RestartSec = "60s";
      };
    };

  };
}

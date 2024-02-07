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

    systemd.services.nix-bitcoin-monitor = {
      description = "Monitoring infrastructure for Bitcoin Core";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      serviceConfig = {
        ExecStart = ''${nix-bitcoin-monitor}/bin/bitcoin-monitor \
          --log-level=${cfg.logLevel} \
          --result-path=${cfg.resultPath} \
          --rpc-host=${cfg.bitcoinRpcHost} \
          --rpc-port=${toString cfg.bitcoinRpcPort} \
          --rpc-user=${cfg.bitcoinRpcUser} \
          ${optionalString (cfg.bitcoinRpcPass != null) "--rpc-password=${cfg.bitcoinRpcPass}" } \
          ${optionalString (cfg.bitcoinRpcPassFile != null) "--rpc-password-file=${cfg.bitcoinRpcPassFile}" } \
        '';
      };
    };

  };
}

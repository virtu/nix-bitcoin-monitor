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

      storeDebugLog = mkEnableOption "storing the debug log" // {
        default = true;
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
      };
      groups.nix-bitcoin-monitor = { };
    };

    systemd.services.nix-bitcoin-monitor = {
      description = "Monitoring infrastructure for Bitcoin Core";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      serviceConfig = {
        ExecStart = ''${nix-bitcoin-monitor}/bin/bitcoin-monitor \
          --log-level ${cfg.logLevel} \
          --result-path ${cfg.resultPath} \
          ${if cfg.storeDebugLog then "--store-debug-log" else "--no-store-debug-log"}
        '';
      };
    };

  };
}

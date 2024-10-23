{
  description = "Monitoring infrastructure for Bitcoin Core";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }: {
    nixosModules.nix-bitcoin-monitor = import ./module.nix self;
  } // flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      pythonVersionParts = (builtins.split "[.]" pkgs.python3.version);
      pythonVersion = "${builtins.elemAt pythonVersionParts 0}.${builtins.elemAt pythonVersionParts 2 }";
      bccEgg = "${pkgs.bcc}/lib/python${pythonVersion}/site-packages/bcc-${pkgs.bcc.version}-py${pythonVersion}.egg";
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication;
    in
    {
      packages = {
        nix-bitcoin-monitor = mkPoetryApplication {
          projectDir = ./.;
          propagatedBuildInputs = with pkgs; [
            # tracepoint support
            bcc
            libbpf
          ];
          wrapPythonScripts = ''
            wrapPythonPrograms "$out/bin" --prefix PYTHONPATH : "${bccEgg}"
          '';
        };

        default = self.packages.${system}.nix-bitcoin-monitor;
      };

      devShells.default = pkgs.mkShell
        {
          inputsFrom = [ self.packages.${system}.default ];
          packages = with pkgs; [ poetry ];
          # add bcc to existing PYTHONPATH
          PYTHONPATH = "${bccEgg}${builtins.getEnv "PYTHONPATH"}";
        };
    });
}

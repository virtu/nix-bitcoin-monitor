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
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication defaultPoetryOverrides;
    in
    {
      packages = {
        nix-bitcoin-monitor = mkPoetryApplication {
          projectDir = ./.;
          overrides = defaultPoetryOverrides.extend
            (final: prev: {
              bcc = prev.bcc.overridePythonAttrs (old: { buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools prev.pytest-runner ]; });
            });
        };

        default = self.packages.${system}.nix-bitcoin-monitor;
      };

      devShells.default = pkgs.mkShell {
        inputsFrom = [ self.packages.${system}.default ];
        packages = with pkgs; [ poetry ];
      };
    });
}

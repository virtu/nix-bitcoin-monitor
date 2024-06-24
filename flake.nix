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
      inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication;
    in
    {
      packages = {
        nix-bitcoin-monitor = mkPoetryApplication {
          projectDir = ./.;
        };

        default = self.packages.${system}.nix-bitcoin-monitor;
      };

      devShells.default = pkgs.mkShell {
        inputsFrom = [ self.packages.${system}.default ];
        packages = with pkgs; [ poetry ];
      };
    });
}

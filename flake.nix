{
  description = "High-Signal News - RSS aggregation and briefing generation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python312
            python312Packages.feedparser
            python312Packages.requests
            python312Packages.beautifulsoup4
            python312Packages.pyyaml
            python312Packages.sgmllib3k
            python312Packages.markdown
            python312Packages.pytest
            git
          ];

          shellHook = ''
            export PYTHONPATH="${./scripts}:''${PYTHONPATH:+:$PYTHONPATH}"
            echo "high-signal-news dev shell ready"
            echo "Python: $(python3 --version 2>/dev/null || true)"
          '';
        };
      });
}

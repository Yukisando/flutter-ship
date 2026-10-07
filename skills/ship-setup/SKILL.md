---
name: ship-setup
description: Prepare this computer to ship Flutter apps with flutter-ship (Ruby, fastlane, Python imaging, the shared encrypted key vault, the Google Play service account). Use on a new machine, when a ship lane says the vault or passphrase is missing, or when the user asks to set up shipping.
---

# Set up a machine for flutter-ship

The plugin root is two folders above this file (`<skill dir>/../..`). Call it `PLUGIN`.

Everything machine-level lives in `~/.ship/`:
- `config.yml` - owner name and vault repo URL
- `vault/` - clone of the private vault repo (encrypted upload keys and Play keys)
- `vault.pass` - the vault passphrase for this machine (never commit it, never print it)

Work through the checks in order. Skip what is already done. Report one line per check at the end.

## 1. Tools

Check each tool. Install only what is missing.

| Tool | Check | Install (Windows) | Install (macOS) |
|---|---|---|---|
| Ruby 3.3 | `ruby -v` | `winget install RubyInstallerTeam.RubyWithDevKit.3.3`, then open a new shell and run `ridk install 3` | `brew install ruby@3.3` |
| Bundler | `bundle -v` | `gem install bundler` | same |
| Python + Pillow + PyYAML | `python -c "import PIL, yaml"` | `python -m pip install pillow pyyaml` | same |
| Flutter, git, gh | `flutter --version`, `gh auth status` (signed in to the account that owns the vault) | - | - |
| Android SDK + an emulator (screenshots) | `adb version`, `emulator -list-avds` | Android Studio > Device Manager > a Pixel AVD | same |

On Windows, RubyInstaller puts Ruby in `C:\Ruby33-x64in`. A shell opened before the install does not see it: prepend that folder to PATH for the session.

Installing software changes the machine. If the permission system blocks an install, give the user the exact command in a `bash` block and continue with the other checks.

## 2. Vault repo and machine config

The vault repo is `<github account>/ship-vault` (the account from `gh auth status`).

1. `gh repo view <account>/ship-vault`.
   - **It exists** (another machine set it up): `git clone https://github.com/<account>/ship-vault.git ~/.ship/vault`, then copy `~/.ship/vault/config.yml` to `~/.ship/config.yml`. Done, go to 4.
   - **It is missing** (first machine ever): create it private and empty: `gh repo create <account>/ship-vault --private --description "Encrypted signing keys for flutter-ship"`. Never create it public. Clone it to `~/.ship/vault`.
2. First machine only: ask for the owner name (for signing certificates) and the default store contact email, then write `~/.ship/config.yml` and copy it to the vault as `config.yml` (it holds no secrets), commit and push:

```yaml
owner_name: Jane Doe
vault_repo: https://github.com/<account>/ship-vault.git
contact_email: hello@example.com          # default store contact
legal:
  generic_url: https://example.com/legal/  # privacy/, tos/, delete-account/ under it
  website_repo: ~/Projects/example.com     # optional: where app-specific pages can be added
  app_path: apps/{slug}/
```

`legal.website_repo` is a local path: on another machine, fix it in `~/.ship/config.yml` if the website repo lives elsewhere.

## 3. Passphrase

- **Vault has `.check.enc`** (passphrase already chosen on another machine): the user copies the passphrase from their password manager into `~/.ship/vault.pass`. Do not ask them to paste it in chat. Open a terminal tab for them (`run_in_terminal` if available) with this PowerShell command, which asks for the passphrase without echoing it:
  `$p = Read-Host 'Vault passphrase' -AsSecureString; [IO.File]::WriteAllText("$HOME\.ship\vault.pass", [Net.NetworkCredential]::new('', $p).Password)`
  On macOS/Linux: `read -rs -p 'Vault passphrase: ' p && printf %s "$p" > ~/.ship/vault.pass && chmod 600 ~/.ship/vault.pass`
- **New vault**: generate a passphrase into the file without printing it:
  `python -c "import secrets,pathlib; pathlib.Path.home().joinpath('.ship','vault.pass').write_text(secrets.token_urlsafe(32))"`
  Then tell the user: "Open `~/.ship/vault.pass`, copy the passphrase into your password manager as *flutter-ship vault*. It is the only thing you need to keep. Every key is recoverable with it plus your GitHub account."

Verify from any app that has `fastlane/ship.yml`: `bundle install`, then `SHIP_LOCAL=$PLUGIN bundle exec fastlane vault_list`. The first run writes `.check.enc` and pushes it.

## 4. Google Play service account

`bundle exec fastlane vault_list` shows `play key default` when it is done. If it is missing, ask the user for the JSON key file path, then run this from an app folder:
`SHIP_LOCAL=$PLUGIN bundle exec fastlane vault_add_play_key path:<file>`

If the user has no key yet:
1. Google Cloud console > IAM > Service accounts > Create, then Keys > Add key > JSON.
2. Enable the "Google Play Android Developer API" for that project.
3. Play Console > Users and permissions > Invite new user: the service account email. Give it these permissions: Admin (all apps), or at least Release apps, Manage store presence, View app information.
4. New service accounts can take up to 24 hours before Play accepts them.

## Why a vault

Upload keys get lost, or differ between machines. Each app's upload key and its passwords are encrypted with AES-256-GCM (key derived with PBKDF2 from the passphrase) and pushed to the private repo. Lanes decrypt the key into a temp folder only for the build. Google Play App Signing holds the real app signing key, so a lost upload key can still be reset in Play Console (App integrity > Upload key > Request reset). The vault exists so that never has to happen.

# MW3 PS3 online fix for accounts made after 2018

> ### There is a tool that does all of this for you
>
> If you would rather not work through the steps below, **PS3 Tools** does the whole thing over your network. Point it at your console and it finds the game, checks whether the fix is already applied, backs the original up to your Desktop, applies the patch, and reads the file back off the console to confirm it worked.
>
> You need a PS3 running custom firmware with webMAN MOD on the same network as your PC, and nothing else. No files to copy off the console, and no scetool command lines to get right.
>
> **[Download PS3 Tools](https://github.com/setsid/ps3-tools/releases/latest)**
>
> The rest of this page is the manual route, and the analysis of what causes the bug. It is still the place to look if you want to do it yourself, or to understand what the tool is doing on your behalf.

---

![platform](https://img.shields.io/badge/platform-PS3-003791)
![tested](https://img.shields.io/badge/tested-BLES01428%20TU%201.24-brightgreen)
![cfw](https://img.shields.io/badge/CFW-Evilnat%204.93%20CEX-lightgrey)

Call of Duty: Modern Warfare 3 on PS3 will not let you play online if your PSN
account was made after late 2018. You reach the lobby, your own name shows, and
about a second later you are back at the multiplayer menu with **Communication
with the Activision servers has been interrupted.** Private match does it too.
Spec Ops is fine.

This is not a server problem and it is not an account ban. It is a bug in the
game binary, shipped in 2011, which only became reachable when Demonware
started turning down newer account identifiers. One instruction causes it. This
repo patches it, and the change is permanent on disk: no memory pokes, no tools
running in the background, no workarounds.

Tested on BLES01428 title update 1.24, Evilnat 4.93 CEX Cobra 8.5, PS3 Slim
CECH-2503B, webMAN MOD 1.47.48q, PAL disc installed to internal SSD. The
patcher locates the fault by instruction pattern rather than a fixed offset, so
it should work on other regions and updates, but I have only verified
BLES01428 1.24.

Patched, MW3 behaves the same as stock MW2 does on the same account, which is
the whole argument for this being the right fix.

There are two ways to apply it. A tool that does the whole thing in one go,
which is the easier route and the one most people should take, and the manual
scetool sequence it wraps. Both are below. The analysis is at the bottom.

---

## The file

One file, `/dev_hdd0/game/BLES01428/USRDIR/default_mp.self`, the multiplayer
binary. Back it up before you touch anything. It is the only way back, and it
cannot be rebuilt from the patched copy.

`default.self`, campaign and Spec Ops, is a separate binary. It is not affected
and nothing here touches it.

`default_mp.self` is not one of the free ones: decrypting it and re-signing it
both need a klicensee, and the usual free one is refused. The tool has it built
in, the manual route below passes it on the command line, and The klicensee at
the end is how it was found.

## The tool

Download `mw3-psn-fix.exe` from the releases page. Nothing to install, nothing
to configure, and scetool is inside it so there is nothing to go and find.

It reads the signing parameters out of your own `default_mp.self`, decrypts it,
applies the patch, re-signs with the values it read rather than the ones in
this readme, and checks the result before it writes anything.

Point it at the game folder holding the file, which on the console is
`/dev_hdd0/game/BLES01428/USRDIR/`. It checks the file is there, fills in an
output folder beside it, and enables the button once everything is in place.
Press it and watch the progress bar. Then carry on at Deploy below.

As soon as the folder is picked it reads the header and shows what it found:
the title ID, that the file is the multiplayer binary, and its size, with the
title update read out of `PARAM.SFO` one level up. That is the point to check
you have the right game and update before anything happens. If it is not
BLES01428 title update 1.24 it says so and still lets you run, because the
patcher matches on the instructions rather than on the title.

Settings holds a log file next to the output, opening the output folder when
finished, and verification after signing, all on by default, plus a scetool
override for anyone who wants a different build or keyset. If your
`default_mp.self` is somewhere other than a game folder, Advanced lets you
point straight at it.

It will not write into the folder the original came from, so it defaults to a
`patched` folder beside it. Everything is built in a temporary folder and only
moved into place once it has passed its checks, so a run that fails leaves you
with nothing rather than with something that half works.

The checks are the parts that are easy to get wrong by hand:

- the file has to be an NPDRM SELF of app type `0x20`, which is what `-c USPRX`
  produces despite the name. `EXEC` gives `0x01` and `UEXEC` gives `0x21`, and
  a file signed as either is perfectly valid and will not load
- the patch site is found by a 16 byte instruction signature, so a binary that
  is not MW3 1.24 multiplayer stops the run rather than being patched at a
  guessed offset
- it reports whether the binary was stock or already patched before it touches
  it, so running it again on a file you have already done re-signs that file as
  it stands rather than patching it twice
- the rebuilt file is decrypted again and compared byte for byte against the
  patched ELF that went into it
- that round trip is then put through the patcher's own check, so the fix has
  to still read as patched after the trip through scetool and not only before
  it
- the key revision, SELF type, licence type, app type, ContentID and CID_FN
  hash all have to come back unchanged. CID_FN is a hash of the filename given
  to `-g`, and getting that wrong gives you a file that is perfectly valid and
  will not load

It stops at the first failure and prints what scetool actually said rather than
a summary of it.

When it finishes it tells you where the file is and what to do with it.

One limitation. scetool has to run with its own folder as the working
directory, and Windows will not accept a UNC path for that. Run the exe from a
local drive rather than from a network share or a `\\wsl$\...` path. It checks
for this at startup and says so rather than failing partway through a job.

## Doing it by hand

The tool is a wrapper around the following. Nothing here is different, it is
just manual, and step 3 is the only part that is not scetool.

You will need:

* scetool 0.2.9 with a keys file containing `appldr` revision `0019` NPDRM. The
  one bundled with the BO2 Eboot Self Builder works.
* `patch-mw3.py` from this repo, and Python 3 to run it
* your own `default_mp.self`, pulled off your console

### 1. Pull the binary off the console

```bash
mkdir -p ~/mw3 && cd ~/mw3
curl -O ftp://YOUR_PS3_IP/dev_hdd0/game/BLES01428/USRDIR/default_mp.self
sha1sum default_mp.self
```

For TU 1.24 that is `1b02160e9daa943789ba5eda7258d1ce47d2df10`. Keep a copy of
this file. It is your rollback.

### 2. Decrypt

The klicensee is not the free one. It is `InfinityWardKey` as raw ASCII, which
Infinity Ward left sitting in the loader stub. See below for how that turned up.

```
scetool.exe -v -l 496E66696E697479576172644B657900 -d default_mp.self default_mp.elf
```

You want `Header decrypted`, `Data decrypted`, `ELF written`.

### 3. Patch

```bash
python3 patch-mw3.py default_mp.elf --check
python3 patch-mw3.py default_mp.elf -o default_mp_patched.elf
```

`--check` should report `offset 00330D20` and `state stock` before you patch.

### 4. Re-sign

```
scetool.exe -t default_mp.self -0 SELF -1 FALSE -s TRUE -2 0019 -5 NPDRM -A 0001000000000000 -6 0004000000000000 -b FREE -c USPRX -f EP0002-BLES01428_00-MW3P000000000124 -g default_mp.self -l 496E66696E697479576172644B657900 -e default_mp_patched.elf default_mp_patched.self
```

Read that ContentID off your own file with `scetool.exe -i default_mp.self`
rather than copying mine.

Two things there are easy to get wrong. `-c USPRX` is what produces app type
`0x20` to match the original, despite the name suggesting otherwise. `EXEC`
gives `0x01` and `UEXEC` gives `0x21`, and neither is right. And `-g` has to be
`default_mp.self`, the name the file has on the console, because it feeds the
CID_FN hash.

Check the result against the original:

```
scetool.exe -i default_mp_patched.self
```

These 5 fields must match the stock file:

```
Key Revision   0x0019
SELF-Type      [NPDRM Application]
Licence Type   0x00000003
App Type       0x00000020
ContentID      EP0002-BLES01428_00-MW3P000000000124
```

### 5. Prove it before you flash it

Decrypt what you just built and confirm the patch survived the round trip:

```
scetool.exe -v -l 496E66696E697479576172644B657900 -d default_mp_patched.self roundtrip.elf
```

```bash
python3 patch-mw3.py roundtrip.elf --check
```

`state patched` means the file is sound.

## Deploy

Close the game fully first, it is the running binary.

The tool writes its output under the console name, so the folder it produces
maps straight across. By hand the file is `default_mp_patched.self` and only
the second line changes.

```bash
curl -T default_mp.self \
  ftp://YOUR_PS3_IP/dev_hdd0/game/BLES01428/USRDIR/default_mp.self.stock

curl -T patched/default_mp.self \
  ftp://YOUR_PS3_IP/dev_hdd0/game/BLES01428/USRDIR/default_mp.self
```

The first line leaves a stock copy on the console beside the patched one, which
makes going back a rename rather than an upload. Convenient, but it is not your
backup: it sits on the drive you are writing to and it goes wherever that drive
goes. The copy you pulled in step 1 is the backup, and it wants to be somewhere
that is not the console.

Verify what landed, against the sha1 of the file you just sent rather than
anything in this readme, since no two re-signed files are alike:

```bash
curl -s ftp://YOUR_PS3_IP/dev_hdd0/game/BLES01428/USRDIR/default_mp.self | sha1sum
```

Launch, Play Online, Find Game, Team Deathmatch.

> **Before you go online.** Lobby modders are active on MW3 PS3 and they will
> rewrite your rank, unlocks and stats without asking. Somebody put me to level
> 80 with everything unlocked in my first match. There is no stats reset in this
> game and nobody is manning Demonware support for a 2011 title, so it cannot be
> undone. If your progression matters, think about that before joining a public
> playlist.

## Rolling back

Push the backup from your PC over the top:

```bash
curl -T default_mp.self \
  ftp://YOUR_PS3_IP/dev_hdd0/game/BLES01428/USRDIR/default_mp.self
```

Renaming `default_mp.self.stock` back over `default_mp.self` on the console is
quicker and does the same thing, as long as it is still there.

Nothing else is touched and nothing is written to flash.

## Reference hashes

BLES01428 title update 1.24.

Stock:

```
7581072  1b02160e9daa943789ba5eda7258d1ce47d2df10  default_mp.self
```

Decrypted, before patching:

```
7578328  8ff8f36b3458b53c99241ad1b66a68e4eb180f04  default_mp.elf
```

Patched, before re-signing:

```
7578328  63d7980c9a73f81ccddb554b6d358a9194bc53aa  default_mp_patched.elf
```

Your re-signed `.self` will not match mine byte for byte unless your signing
parameters are identical, which is fine. The check that matters is the round
trip in step 5, which the tool does for you.

---

## What you end up with

Patched MW3 behaves **exactly the same as stock MW2 does on the same account**.
Not similar. The same.

| | stock MW2 | stock MW3 | patched MW3 |
|---|---|---|---|
| Profile lookup | fails, error 110 | fails, error 110 | fails, error 110 |
| Reaches lobby | yes | yes | yes |
| Stays in lobby | yes | **no, kicked to menu** | yes |
| Lobby roster names | `Matched Player` | n/a | `Matched Player` |
| Scoreboard names | correct | n/a | correct |
| Stats and rank save | yes | n/a | yes |
| Plays online | yes | **no** | yes |

MW2 has never needed patching and nobody thinks it is broken, and it sits there
doing the identical thing. I am not making MW3 do something strange, I am making
it do what its own sister title already does when the server gives it the same
answer.

## What actually goes wrong

On entering a competitive lobby, MW3 asks Demonware for profile info for everyone
on the roster, up to 18 entries at a time. On an affected account the server
replies with `BD_INVALID_USER_ID`, error 110.

The handler that receives that reply treats **any** non zero task error as fatal.
It calls `Com_Error` at severity 1, which is `ERR_DROP`, and that is what boots
you back to the menu.

Private match fails the same way, and a private match roster contains only you.
So the identifier being rejected is your own.

## Why this is a bug in MW3, not just a dead backend

This is the part that settled it.

I put MW2 on the same console with the same account, completely stock. It joins
straight away. Watch the lobby and you can see player names appear for about 2
seconds and then flip to `Matched Player`.

Same lookup, same failure, same identifier, in a game from a year earlier on the
same Demonware SDK. MW2 shrugs and carries on. MW3 kills the session.

The profile data is cosmetic. MW3's mistake was routing it through a generic
handler where every error is fatal. Activision's own support page lines up: MW2
from 2009 and Black Ops from 2010 lose progression but stay playable, while MW3
from 2011 and Black Ops 2 from 2012 become unplayable.

So the `Matched Player` placeholder after patching is not damage caused by the
patch. It is what the engine does when profile data is unavailable, and stock MW2
does exactly the same. Real names still show on the scoreboard because those come
from the peer to peer session, not the profile service.

## The patch

```
vaddr        0x00340D20
file offset  0x00330D20
before       607C0000    ori r28, r3, 0
after        3B800000    li  r28, 0
```

One instruction. It is four bytes wide and two of them actually change, the low
half being zero either way.

The error code is discarded as it is read, so the fatal branch never runs. The
task then reports success with 0 records, the caller's fill loop runs 0 times,
and the task is freed on the path it already had. The function containing this
instruction has exactly 1 caller, so nothing outside the profile lookup changes.

## Everything else out there is a workaround

* **XUID spoofing.** You borrow somebody else's identifier and play as them. It
  is the fix most guides push. It didn't sit right with me. It isn't your
  account, it isn't your identity, and it fixes nothing.
* **Mod menu account fix.** Changes your name. Same idea in a nicer wrapper.
* **Modded hosts.** Somebody else has the check removed on their console and you
  join them. No good for hosting, and no good when nobody is running one.
* **The X spam race.** Hammer X from the multiplayer menu through to create a
  class and you get in about 3 times out of 4. It is a timing race, not a fix.

None of them touch the cause. This removes the defect and changes nothing else.

Be clear on what it does and does not do. It does **not** make Demonware accept
your identifier. The server still rejects it. What it fixes is MW3 killing your
session over a lookup that never mattered.

## The klicensee

Worth writing down because everybody hits this wall.

`default_mp.self` is key revision `0x0019`, NPDRM, licence type 3 which reads as
free. The standard free klicensee `72F990788F9CFF745725F08E4C128387` is rejected
by both scetool and RPCS3, and there is no rif or rap on the console to derive
one from, so it looks unsolvable. It is not.

MW3's `EBOOT.BIN` is a 74KB loader stub whose only job is to spawn
`default_mp.self`, which means it has to supply the klicensee. And `EBOOT.BIN` is
app type `0x21`, which scetool decrypts with no klicensee at all:

```
scetool.exe -d EBOOT.BIN EBOOT.elf
```

In the decrypted stub, `0x000103DC` loads `0x0001D4B0` into r3 immediately before
the spawn call. `sceNpDrmProcessExitSpawn` takes the klicensee as its first
argument, and at `0x0001D4B0` sits 16 bytes of plain ASCII:

```
49 6E 66 69 6E 69 74 79 57 61 72 64 4B 65 79 00     InfinityWardKey.
```

So the key is `496E66696E697479576172644B657900`. It sits 16 bytes before the
string `Trying to boot NPDRM [%s]`, in the clear, in a 74KB file.

## Known limitations

* Other players show as `Matched Player` in the lobby panel. Names are correct on
  the scoreboard. Not caused by the patch. Stock MW2 on the same account does the
  identical thing.
* I saw 1 host migration hang during testing, sent 100% of blocks and never came
  back. Unclear whether that is the patch or MW3 host migration being MW3 host
  migration.
* Multiplayer only. `default.self` (campaign and Spec Ops) is untouched, and Spec
  Ops online was never affected.

## Files

* `patch-mw3.py` binary patcher. Locates the site by a 16 byte signature rather
  than a fixed offset, refuses if it matches more than once, cross checks against
  the program headers, and will not double patch. `--check` and `--restore`
  included.
* `docs/analysis.md` how the bug was found, addresses, call chain, the ruled out
  list, and instrumentation notes
* `docs/mw3-bdlobby-error-codes.md` the full `BD_*` enum, 189 entries, pulled out
  of the code to name table in the binary. Shared across Call of Duty titles, so
  useful well beyond MW3.

## Credits

scetool is naehrwert's. A compiled copy and its keys are bundled inside the exe
so it runs without any setup. This project is not affiliated with it, and
nothing here modifies it.

## Licence

Do what you like with it.

# Analysis

MW3 PS3, BLES01428, title update 1.24, `default_mp.self`.

Vaddr is file offset plus `0x10000` throughout.

---

## The failure

On entering a competitive lobby the game issues a batch `bdProfileInfo` request
for the roster, up to `0x12` entries. Demonware answers with
`BD_INVALID_USER_ID`, code 110, on accounts created after late 2018.

`FUN_00340C8C` receives the result:

```c
int FUN_00340C8C(task_t *t, void *out, int *count) {
    if (!t || !t->obj || !FUN_0034507C(t->localClient)) return 2;
    FUN_00345DC4(t->localClient);
    r27 = t->obj->vtbl[1]();          // poll status
    r28 = FUN_0043F010(t->obj);       // *(int*)(obj + 0x38), the error code
    if (r27 == 2) {
        n = FUN_0043EFA8(t->obj);     // records returned
        memset(out, 0, *count * 16);
        *count = 0;
        for (i = 0; i < n; i++) { ... }
    }
    if (r28 != 0) {                                        // 0x340DC0
        FUN_001F5BF8(t);
        if (r28 == 1) FUN_0036436C(1, "XBOXLIVE_TOOMANYTASKS");
        FUN_00346244(r28, buf, 0x40);                      // name it, then discard
        FUN_002F2B88(t->localClient);
        FUN_0036436C(1, "XBOXLIVE_LIVEERROR");             // 0x340E0C
    }
    return FUN_003463B0(r27, r28);
}
```

`FUN_0036436C` tail calls `Com_Error` at `0x3643F8`. Severity 1 is `ERR_DROP`.

The caller is the per frame task pump `FUN_002F1350`, which walks the queue at
`0x01BBBD50` (`0x20` entries, stride `0x88`) and dispatches this task at
`0x2F1598` with an in out count seeded to `0x12`.

On success the caller writes one 32 bit value per player at
`base + 0x98 + idx * 0x50`, keyed by the 64 bit user ID in each 16 byte record.
Cosmetic roster data. Nothing the join depends on.

### Why nopping the popup was never enough

`FUN_003463B0(r27, r28)` returns 1 only when `r27 == 2 && r28 == 0`. With
`r28 = 110` it returns 0 or 2, the caller's `== 1` test at `0x2F15A0` fails, and
the join is dead regardless of whether the dialog appeared. Removing the 5
`XBOXLIVE_LIVEERROR` call sites suppresses the message and the `ERR_DROP` and
still leaves you unable to play.

Discarding the error at `0x340D20` avoids that, because the success path then
runs with 0 records and the task is freed normally by the caller at `0x2F1654`.

---

## Key addresses

| Address | Meaning |
|---|---|
| `0x00340D20` | the patch site, `ori r28, r3, 0` |
| `FUN_00340C8C` | profile task handler, 1 caller |
| `FUN_002F1350` | per frame task pump |
| `FUN_0043F010` | `bdRemoteTask::getErrorCode`, `*(int*)(p+0x38)`, 61 callers |
| `FUN_0043EFA8` | record count on a completed task |
| `FUN_00346244` | `BD_*` code to name, table at `0x731E3C`, names at `0x732130` |
| `FUN_0036436C` | wrapper, tail calls `Com_Error` |
| `FUN_001F6A08` | `Com_Error` |
| `FUN_002985D8` | `Q_strncpyz`, calls real `strncpy` at `0x0049D9C0` |
| `0x0058F750` | vtable of the failing task, RTTI `13bdProfileInfo` inline before it |
| `0x01BBBD50` | task queue, `0x20` entries, stride `0x88`, object at `+8` |
| `0x01BBBC28` | local client records, stride `0x48` |
| `0x011F1140` | `Com_Error` message buffer, `0x1000` bytes |
| `0x011F1088` | last `Com_Error` severity |
| `0x011F1134` | error counter, incremented by `Com_Error`, decremented by `Com_Frame` |

Local client record layout at `0x01BBBC28 + index * 0x48`:

```
+0x00  sign in state, 2 = signed in
+0x04  PSN online ID, 0x24 byte field
+0x28  8 byte identifier
+0x30  same value as 16 char lowercase hex, NUL terminated
```

---

## How it was found

`FUN_0043F010` is 3 instructions and every Demonware task result passes through
it. Hooked at the entry with a stub in the executable padding at `0x71E000`,
filtering on a non zero return so the success path costs 2 instructions, logging
the code, the object pointer and the caller's return address.

First clean run: code `0x6E`, vtable `0x0058F750`, return address `0x00340D1C`.
That is 110, `bdProfileInfo`, and `FUN_00340C8C` respectively. Reproduced on a
second run with a different heap pointer and identical everything else.

### The trap that cost a session

Do not put log buffers anywhere in `0x011F1140` to `0x011F213F`.

That range is the `Com_Error` message buffer. When `Com_Frame` localises the
message it uses `Q_strncpyz` at size `0x1000`, which calls real `strncpy`, which
zero pads the destination to the full length. Every counter in that range is
wiped by the exact event being measured, then repopulated by the reconnect that
follows, so the numbers read back looking perfectly healthy while describing
completely the wrong thing.

`0x02200000` was used instead, verified with a canary across a full join and kick
cycle. `0x02280000` is live game data.

### Other traps

* PS3MAPI attaches per process. Spec Ops and campaign run `main_default.self`,
  multiplayer runs `main_default_mp.self`. Switching modes silently invalidates
  every address. Verify with `0x43F010` reading
  `80 63 00 38 7C 63 07 B4 4E 80 00 20` before trusting a read.
* `0x340D1C` is `cmpwi r27, 2` and `0x340D24` consumes that result, so any stub
  hooked at `0x340D20` must not touch CR0.
* The compiler emits `addic` (opcode 12) for the low half of an absolute address,
  not `addi` (opcode 14). Scripts that only decode opcode 14 find nothing. Ghidra
  handles it correctly.
* Duplicate string literals exist. `XBOXLIVE_LIVEERROR` is at both `0x55FF10`
  and `0x55B0F4`, so scanning for one address misses call sites using the other.

---

## Ruled out

Everything below was chased and eliminated. Listed so nobody repeats it.

| Theory | How it died |
|---|---|
| The BO2 `crm %lld %s` formatter bug | String absent from the binary entirely |
| `@PLATFORM_NO_DEMONWARE` gate | All 3 gate globals pass at failure time |
| 5 second task timeouts | Both patched to `0x7530`, no change |
| Connection state check `FUN_002FFD08` | Forced true, no change |
| XUID validation in the client | The only XUID code is a writer and a printf warning. `FUN_001F44B4` has explicit mismatch recovery |
| `Com_Error` not running | It does run. The earlier negative was a wiped counter |
| Lobby state machine `0x01CF1418` | `FUN_0033B7B8` is the state machine, `0x33B7B8` to `0x33C3E8`, one function. It reaches `0x0B` and connects fine. The `0x0B` to 9 to `0x0B` bounce is an ordinary re establish |
| bdAuth | Step 9 checks the auth result against `0x2BC`, which is 700, `BD_AUTH_NO_ERROR`. Measured 700 three times per join |
| Step `0x0A` connection poll | `FUN_00452564` returns `*(obj->0x78 + 0x40)`, object cached at `0x01CF1DD8`. Returns 2, connected |

---

## Open questions

**Why the server rejects the identifier.** The local identifier on the affected
account is `CA141E6DA8286F99`, high bit set. Demonware's backend was Java, where
`long` is signed, so a profile service validating `userId > 0` would reject it.
That is a guess and it predicts failure for roughly half of all accounts
regardless of creation date, which conflicts with the observed 2018 boundary. It
needs 1 identifier read from a working account to test, which needs a second
account.

There is a competing explanation. The NGU tool description says working accounts
are ones that **played MW3 before** the PSN name change feature existed, not
merely accounts created before it. If the discriminator is whether a profile
record already exists server side, the clean date boundary follows naturally.
Against that, `BD_NO_PROFILE_INFO_EXISTS` is a separate code, 800, and the
observed code is 110.

The identifier is not derived from the online ID. 63 hash variants across
md5, sha1 and sha256 with 8 padding widths, big and little endian and xor folded,
all miss. It is supplied by the NP layer or issued by Demonware.

**Restoring real roster names.** Excluding the local identifier from the request
should let the batch succeed for everyone else. The request is built by
`FUN_0043E974`, the bdLobby `profilesInfo` service, string at `0x578350`, single
caller at `0x353AC0`. That is an enhancement rather than a repair, since MW2
demonstrates that tolerating the failure is sufficient.

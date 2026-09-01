# Parts list

Everything needed to build one rig. Links are the original sourcing links
(cleaned of tracking params); price/availability will drift, treat them as
"this is the part" rather than "buy from exactly here."

## Compute, camera, display

| Part | Spec | Source |
|---|---|---|
| Jetson Nano | B01 devkit carrier board | (already on hand — not sourced from a link) |
| Camera | Raspberry Pi CSI camera module | any CSI camera compatible with the Nano's connector; not spec'd beyond that |
| Display | Hosyond 7" IPS touchscreen, 1024×600, HDMI + USB-C | [amazon.com/dp/B0BKGCB18T](https://www.amazon.com/dp/B0BKGCB18T) |

## Firing circuit

| Part | Spec | Source |
|---|---|---|
| Solenoid valve | U.S. Solid, 1/8" NPT, 12V DC, 2-way normally closed | [amazon.com/dp/B06WLMX88B](https://www.amazon.com/dp/B06WLMX88B) |
| Relay module | ANMBEST 1-channel opto-isolated, 12V coil, high/low trigger select | [amazon.com/dp/B08PNHHC65](https://www.amazon.com/dp/B08PNHHC65) |
| Solenoid/relay battery pack | Aobao 8×AA holder, 12V, built-in ON/OFF switch and leads (sold as a 3-pack) | [amazon.com/dp/B09L7R2159](https://www.amazon.com/dp/B09L7R2159) |
| Arm switch | RobotShop RB-Spa-709, illuminated toggle with missile cover, 12V 20A contacts | [robotshop.com/products/illuminated-toggle-switch-red](https://www.robotshop.com/products/illuminated-toggle-switch-red) — RobotShop's own page doesn't give a pinout; see [wiring.md](wiring.md#the-arm-switch) for the terminal ID Jeff worked out with a multimeter |

Small electronics to have on hand, no specific vendor — any electronics
supplier: **1kΩ resistor** (arm-switch pull-up — see
[wiring.md](wiring.md#the-arm-switch) for why 1kΩ and not the more usual
10kΩ), **1N4007 flyback diode** (across the solenoid coil, if the relay board
doesn't already have one), **1-2A inline fuse** (12V rail), two small
screw-terminal distribution blocks (fan out the battery pack's + and − to the
relay and solenoid).

## Pneumatics — barrel adapter

Steps the solenoid's 1/8" NPT outlet up to a 1/2" PVC barrel. No specific
vendor — generic plumbing/hardware store parts (see
[wiring.md](wiring.md#the-barrel) for the assembly order):

- 1/8" NPT male-male nipple
- Reducer bushing, 1/2" NPT male × 1/8" NPT female
- PVC adapter, 1/2" Schedule 40, female adapter, slip × FPT
- 1/2" Schedule 40 PVC pipe, cut to barrel length
- PTFE tape (NPT joints) and PVC cement (the slip joint — not a dry press-fit)

## Enclosure

Printed, not purchased — see [hardware/enclosure.scad](../hardware/enclosure.scad).
PETG or ASA for any part with a snap tab (PLA gets brittle under repeated
flexing); PLA is fine for the base plate and pipe clips.

## Not used in round one

| Part | Spec | Source |
|---|---|---|
| Pan/tilt kit | Lynxmotion aluminium pan and tilt kit | [robotshop.com/products/lynxmotion-pan-and-tilt-kit-aluminium2](https://www.robotshop.com/products/lynxmotion-pan-and-tilt-kit-aluminium2) |

Bought at project start, deliberately shelved — see "Not yet built" in
[README.md](../README.md). The `on bore` interlock is the seam it will
eventually attach to.

## Provenance

The Amazon/RobotShop links above trace back to the project's original
planning note (outside this repo, in Jeff's Obsidian vault) — this file is
that note's hardware list, reconciled with what `docs/wiring.md` has since
confirmed against the physical parts (part numbers, pinouts, the exact
resistor value) as the build actually came together.

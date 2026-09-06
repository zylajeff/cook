// ============================================================
// COOK rig enclosure v2 — single rectangular box, fastener-free:
// no screws, inserts, nuts, or glue anywhere. Two halves TELESCOPE
// together lengthwise (front shell's rear collar slides inside the
// rear shell's front mouth) and lock with a press-fit snap bump —
// pull apart by hand for service, no tool needed.
//
// Open in OpenSCAD (openscad.org). PLACEHOLDER dimensions below are
// marked "MEASURE YOURS" — confirm against your actual parts, then
// F5 (preview) before F6 (render) / STL export.
//
// Print each part as a SEPARATE STL: set exactly one render_* flag
// true, F6, export, repeat. render_assembly shows both halves
// together, telescoped in, for a fit sanity check only.
//
// Material: PETG or ASA — the snap bump needs to flex/spring back
// without going brittle. PLA is fine if you don't mind reprinting it
// once the bump wears out.
//
// AXIS CONVENTION, read this before editing anything: X = box width
// (left-right, matches face_w), Y = box height (up-down, matches
// face_h), Z = box depth (front-to-back). The front face lives in
// the XY plane at Z=0 for front_shell(); the rear shell's open mouth
// (which receives the collar) is at its own Z=0, and its closed back
// cap is at Z=rear_shell_depth. Anything that "stands on the floor"
// (Nano, battery, protoboard) has its footprint in X-Z and extends
// upward in +Y from the floor at Y=-inner_h/2 — an earlier draft of
// this file got that backwards (cut pockets as slices across the
// depth axis instead of as recesses in the floor) and I only caught
// it by re-deriving the axes by hand, not by rendering.
//
// I do not have OpenSCAD running in the environment this was written
// in (you confirmed you have it locally) — everything below is
// worked out from the numbers, not rendered. Spots flagged inline
// with "FLAG:" are the ones most likely to need a nudge once you
// actually preview it.
// ============================================================

// ---- WHICH PART TO RENDER ----
render_front_shell = false;
render_rear_shell  = true;
render_assembly    = false;

// ---- GLOBAL TOLERANCES ----
wall      = 2.4;   // shell wall thickness (~6 perimeters at 0.4mm nozzle)
fit_gap   = 0.25;  // clearance budget for the telescoping collar (per side)
corner_r  = 3;     // outer corner rounding
$fn       = 48;

// ============================================================
// MEASURE-AND-CONFIRM: component footprints
// Confirmed from spec sheets: display, camera, battery pack, switch
// panel-hole diameter. Everything else is a reasonable placeholder —
// measure your actual part and edit before slicing.
// ============================================================

// -- Display: Hosyond 7", CONFIRMED from spec sheet --
disp_l = 164.9; disp_w = 102.0; disp_h = 15.15;
disp_active_l = 154.21; disp_active_w = 85.92;
disp_sleeve_clr = 0.8;  // total clearance around the display's outer edge in its retaining sleeve (0.4mm/side) -- looser than fit_gap (meant for small parts), since a slide-fit this size needs more margin for print tolerance; loosen further if it doesn't slide in easily

// -- Camera: Raspberry Pi Camera Module v2, CONFIRMED standard footprint --
cam_pcb_l = 25; cam_pcb_w = 24; cam_pcb_h = 9;
cam_hole_pitch = 21;   // the two M2 mounting holes, this far apart, centered on the board
cam_hole_d     = 2.4;  // clearance for an M2 self-tapper / heat-set insert-free press fit
cam_lens_d     = 9;    // front clearance hole for the lens barrel + ribbon strain relief

// -- Jetson Nano B01 devkit, typical published carrier-board spec —
//    reasonably reliable (it's a standard part), but verify against
//    yours before slicing, especially height with your heatsink. --
nano_l = 100; nano_w = 80; nano_h = 29;

// -- Aobao 8xAA battery holder, CONFIRMED from the listing:
//    12.6 x 7.1 x 2.0cm (L x W x H), 14cm leads each. --
batt_l = 126; batt_w = 71; batt_h = 20;
batt_lead_len = 140;

// -- Small protoboard you'll solder the relay/fuse/resistor circuit
//    to (PLACEHOLDER — size to whatever board you actually buy) --
pcb_l = 70; pcb_w = 50;
pcb_thickness = 15;  // PLACEHOLDER — rough guess for a populated board (relay, terminal blocks); measure yours

// -- Firing (arm) switch, SparkFun "Toggle Switch and Cover -
//    Illuminated (Red)". Panel hole CONFIRMED at 12mm from the
//    listing. Behind-panel depth is still not published anywhere —
//    PLACEHOLDER, measure the body + missile-cover mechanism with
//    calipers before slicing. --
switch_bushing_d = 12;  // CONFIRMED
switch_body_len  = 35;  // PLACEHOLDER — clearance needed behind the panel for the switch + lugs + missile cover mechanism

// -- 12g CO2 cartridge, typical published dims for a threaded 12g —
//    verify against your actual brand, some run longer. --
co2_d       = 12.6;  // clearance diameter (cartridge body + a hair)
co2_len     = 68;
co2_count   = 3;      // horizontal channels, stacked vertically — one cartridge each, lying flat

// ============================================================
// FRONT-FACE LAYOUT
// Display centered vertically in its own zone; firing switch to its
// right; camera centered above the display. All zone maths live here
// (not buried in a module) so front_shell() and the assembly preview
// use the exact same numbers.
// ============================================================
side_margin   = 12;   // left/right edge margin
disp_gap      = 15;   // gap between display's right edge and the switch zone
switch_zone_w = 40;   // width reserved for the switch mount

top_margin    = 12;
cam_zone_h    = 34;   // height reserved for the camera mount
cam_gap       = 10;   // gap between camera zone and display's top edge
bottom_margin = 12;

face_w = side_margin + disp_l + disp_gap + switch_zone_w + side_margin;
face_h = top_margin + cam_zone_h + cam_gap + disp_w + bottom_margin;

box_w = face_w;  // outer cross-section, shared by both shells so the
box_h = face_h;  // assembled box has one continuous flush surface

// Display center, measured from the face's own center origin.
disp_cx = -face_w / 2 + side_margin + disp_l / 2;
disp_cy = -face_h / 2 + bottom_margin + disp_w / 2;

// Switch center, to the right of the display, vertically centered
// on the display so it reads as part of the same control row.
switch_cx = disp_cx + disp_l / 2 + disp_gap + switch_zone_w / 2;
switch_cy = disp_cy;

// Camera center, horizontally centered on the display, in its own
// zone above it.
cam_cx = disp_cx;
cam_cy = face_h / 2 - top_margin - cam_zone_h / 2;

// ============================================================
// TELESCOPING COLLAR
// The two shells share box_w x box_h as their OUTER cross-section
// everywhere except the front shell's last collar_len, which steps
// its OUTER envelope down by (wall + fit_gap) per side so it slides
// inside the rear shell's constant-size inner cavity. Short collar
// walls end up thinner than the main body (wall - fit_gap) — fine
// for a 14mm span, still >1.5mm at these numbers.
//
// FLAG: reasoned from the numbers, not rendered. If the collar
// prints snug/loose, the one knob to turn is fit_gap — don't rescale
// box_w/box_h, everything else depends on those.
// ============================================================
collar_len = 14;

collar_outer_w = box_w - 2 * (wall + fit_gap);
collar_outer_h = box_h - 2 * (wall + fit_gap);

front_clear_depth = 32;   // behind the face plate: display PCB + camera standoff + wiring slack
front_shell_depth = front_clear_depth + collar_len;

// ============================================================
// REAR SHELL DEPTH — components mount flush against the back wall,
// not on the floor. Depth is driven by whichever part sticks out the
// farthest (Nano at 29mm, the tallest), not by anyone's length or
// width — that's what let this shrink from a 240mm rear shell (three
// parts stacked front-to-back by their footprints) down to about
// 60mm. Standoffs lift each board off the wall by standoff_h; the
// wiring_margin beyond that keeps the nearest component comfortably
// clear of the inserted collar (checked below, not just assumed).
// ============================================================
standoff_h       = 5;    // gap between the back wall and the underside of each mounted board
wiring_margin    = 19.2; // clearance ahead of the tallest component, before the collar zone starts -- sized to land the assembled box at exactly 4in total depth; the rest of this section's math is unchanged, so this is the one knob that moved
component_max_h  = max(nano_h, max(batt_h, pcb_thickness));  // 29mm, Nano

rear_clear_depth = wiring_margin + standoff_h + component_max_h;
rear_shell_depth = collar_len + rear_clear_depth + wall;
back_cap_inner_z = rear_shell_depth - wall;

// FLAG: reasoned from the numbers, not rendered. The check that
// actually matters here: back_cap_inner_z - standoff_h - component_max_h
// should land at collar_len + wiring_margin, comfortably ahead of the
// inserted collar — recompute this by hand if you change any of
// standoff_h/wiring_margin/component_max_h/collar_len, since nothing
// enforces it automatically.

// ============================================================
// BUILDING BLOCKS
// ============================================================

// Rounded rectangular box, solid, extruded up from z=0.
module rounded_box(l, w, h, r) {
    linear_extrude(h)
        hull()
            for (x = [-1, 1], y = [-1, 1])
                translate([x * (l / 2 - r), y * (w / 2 - r)])
                    circle(r = r);
}

// CO2 hopper: ONE gravity-fed magazine, not a rack you can reach into
// at any level. Load from the open top; cartridges lie on their
// sides (long axis along X) and stack directly on each other inside
// a shaft that's solid on ALL FOUR sides — back, both ends, AND the
// front — for every level except the bottom one. Only the bottom
// slot_h of the front is left open: that's the single access point.
// Pull the bottom cartridge out and the whole stack above drops down
// one position under gravity, refilling it — you physically can't
// reach in and pull a middle or top one instead. Origin at the
// housing's own bottom-back corner, +X/+Y/+Z.
module co2_hopper(l, stack_h, depth, wall_t, slot_h) {
    union() {
        cube([l, stack_h, wall_t]);                  // back wall, against the box
        cube([l, wall_t, depth]);                     // bottom wall
        cube([wall_t, stack_h, depth]);                // left end wall
        translate([l - wall_t, 0, 0])
            cube([wall_t, stack_h, depth]);            // right end wall
        translate([0, slot_h, depth - wall_t])
            cube([l, stack_h - slot_h, wall_t]);        // front wall, everywhere ABOVE the bottom access slot
    }
}

// Snap bump: a small dome the front shell's collar wears on the
// outside, mating into snap_dimple() cut into the rear shell's inner
// collar wall. Press-fit, not a flexing cantilever — simplest thing
// that reliably retains a telescoping joint like this one.
module snap_bump(r = 2.2) {
    sphere(r = r);
}

module snap_dimple(r = 2.2, clr = 0.15) {
    sphere(r = r + clr);
}

// Snap peg: pushes through a board's own mounting hole and retains
// it there — shaft sized for a light slide fit, then a barb that
// bulges wider than the hole so the board has to flex slightly to
// pop over it, and a tapered tip so it starts easily. Once seated,
// the barb sits proud on the far side of the board and resists it
// coming back off in any direction, including sliding down under
// gravity — unlike a plain post, which a vertically-mounted board
// would just slide off. hole_r is a PLACEHOLDER (1.6mm, generic M3
// clearance) — measure the board's actual hole diameter before
// slicing. Origin at the peg's own base, +Z.
module snap_peg(shaft_h, hole_r = 1.6, barb_extra = 0.4) {
    shaft_r = hole_r - 0.2;
    barb_r  = hole_r + barb_extra;
    cylinder(h = shaft_h, r = shaft_r);
    translate([0, 0, shaft_h])
        cylinder(h = 1.2, r1 = shaft_r, r2 = barb_r);
    translate([0, 0, shaft_h + 1.2])
        cylinder(h = 1.0, r1 = barb_r, r2 = shaft_r * 0.6);
}

// Four snap pegs for a board WITH real mounting holes (Nano,
// protoboard): footprint fx x fy, centered at (cx, cy), pegs inset
// from the true corners by `inset` — a stand-in for the board's own
// hole pattern, which isn't known yet. Move these to match the real
// hole positions once you've measured the board; the peg shape
// itself (snap_peg()) doesn't need to change.
module wall_snap_pegs(cx, cy, fx, fy, z0, standoff_h, inset = 8) {
    for (x = [-1, 1], y = [-1, 1])
        translate([cx + x * (fx / 2 - inset), cy + y * (fy / 2 - inset), z0 - standoff_h])
            snap_peg(standoff_h);
}

// Shelf bracket for a board with NO mounting holes (the battery
// pack): a horizontal ledge it physically rests on — actual support
// against gravity, which a peg-in-a-hole can't provide here since
// there's no hole — plus a low front lip so it can't slide forward
// off the shelf and out of the box. fx = shelf width (X), depth =
// how far it protrudes off the wall (should clear standoff_h + the
// battery's own height), bottom_y = where the battery's underside
// should sit. Origin at z0 = back_cap_inner_z, extending toward the
// mouth (-Z).
module wall_shelf(cx, bottom_y, fx, depth, z0, wall_t, lip_h = 4) {
    translate([cx - fx / 2, bottom_y - wall_t, z0 - depth])
        cube([fx, wall_t, depth]);                        // the shelf itself — top surface lands exactly at bottom_y
    translate([cx - fx / 2, bottom_y, z0 - depth])
        cube([fx, lip_h, wall_t]);                         // stop at the outer edge — battery slides in from outside, along the shelf, until it hits this
}

// Retaining sleeve for a flat panel mounted behind a front-face
// window (the display): a snug frame surrounding all FOUR edges of
// its outer footprint, not just a bottom shelf — a screen needs to
// stay precisely aligned with its cutout, not merely "not fall out",
// so it's captured on every side rather than just resting on one.
// Slides in from the open back of the shell during assembly until
// its front bezel meets the thin shoulder already cut around the
// active-area window (see front_shell()); this sleeve is what stops
// it sliding down under gravity or rattling side to side afterward,
// which that shoulder alone never did. z0 = the face (z=0 side),
// extends into the shell in +Z.
module display_sleeve(cx, cy, l, w, depth, wall_t, clr) {
    difference() {
        translate([cx, cy, 0])
            linear_extrude(depth)
                square([l + 2 * wall_t + clr, w + 2 * wall_t + clr], center = true);
        translate([cx, cy, -0.1])
            linear_extrude(depth + 0.2)
                square([l + clr, w + clr], center = true);
    }
}

// ============================================================
// PART 1 — FRONT SHELL
// Carries the control face (display, switch, camera). Its rear
// collar_len telescopes into the rear shell. The CO2 hopper lives on
// the rear shell instead (see PART 2) — it needs to run most of the
// box's depth for the cartridges to lie flat, and putting the whole
// thing on one shell avoids splitting a channel across the parting
// line. Print face-down, no supports needed for the face cutouts.
// ============================================================
module front_shell() {
    difference() {
        union() {
            // Outer solid: main body full box_w x box_h for
            // front_clear_depth, stepping down to the collar's
            // smaller cross-section for the last collar_len.
            rounded_box(box_w, box_h, front_clear_depth, corner_r);
            translate([0, 0, front_clear_depth])
                linear_extrude(collar_len)
                    hull()
                        for (x = [-1, 1], y = [-1, 1])
                            translate([x * (collar_outer_w / 2 - corner_r),
                                       y * (collar_outer_h / 2 - corner_r)])
                                circle(r = corner_r);

            // Snap bumps near the collar's leading tip, on its two
            // long (width) faces.
            for (side = [-1, 1])
                translate([side * (collar_outer_w / 2), 0, front_shell_depth - 4])
                    rotate([0, side > 0 ? 90 : -90, 0])
                        snap_bump();
        }

        // Hollow the interior out from behind the front face. Two
        // pieces matching the two outer pieces above: main body
        // cavity, then the collar's own (smaller) cavity so its
        // walls come out to wall - fit_gap, not wall.
        translate([0, 0, wall])
            linear_extrude(front_clear_depth)
                hull()
                    for (x = [-1, 1], y = [-1, 1])
                        translate([x * (box_w / 2 - wall - corner_r),
                                   y * (box_h / 2 - wall - corner_r)])
                            circle(r = corner_r);
        translate([0, 0, front_clear_depth])
            linear_extrude(collar_len + 0.2)
                hull()
                    for (x = [-1, 1], y = [-1, 1])
                        translate([x * (collar_outer_w / 2 - (wall - fit_gap) - corner_r),
                                   y * (collar_outer_h / 2 - (wall - fit_gap) - corner_r)])
                            circle(r = corner_r);

        // -- Front face cutouts, all in the z=0 face --
        // Display window: cutout through the face, sized to the
        // ACTIVE area so the bezel itself hides the display's own
        // frame. The thin ring of material left around this window
        // (between it and the display's full outer edge) is what the
        // display's front bezel rests against — see display_sleeve()
        // below for what actually keeps it there instead of sliding
        // down under gravity.
        translate([disp_cx, disp_cy, -0.1])
            linear_extrude(wall + 0.2)
                square([disp_active_l, disp_active_w], center = true);

        // Switch panel cutout.
        translate([switch_cx, switch_cy, -0.1])
            cylinder(h = wall + switch_body_len, r = switch_bushing_d / 2);

        // Camera lens + mounting-hole cutouts.
        translate([cam_cx, cam_cy, -0.1])
            cylinder(h = wall + 0.2, r = cam_lens_d / 2);
        for (x = [-1, 1])
            translate([cam_cx + x * cam_hole_pitch / 2, cam_cy, -0.1])
                cylinder(h = wall + 0.2, r = cam_hole_d / 2);

        // CSI ribbon channel: a slot from just behind the camera
        // mount down into the main cavity, wide enough for the flex
        // ribbon to bend through without kinking.
        // FLAG: 10mm is a guess at what a CSI ribbon needs to bend
        // through without kinking — widen this in the preview if
        // your ribbon looks pinched.
        translate([cam_cx - 5, cam_cy - cam_zone_h / 2, wall])
            cube([10, cam_gap + 4, front_clear_depth]);
    }

    // Camera snap pegs: added AFTER the difference() above (a sibling
    // statement, implicitly unioned with it), same reasoning as the
    // rear shell's mounted boards — geometry this close to the face
    // would otherwise fall inside the cavity cut and get removed.
    // Unlike the Nano/battery/protoboard, this hole pattern IS
    // confirmed (Camera Module v2's real 21mm pitch), so these pegs
    // are a real fit, not a placeholder — short shaft (4mm) keeps the
    // board close to the face so its lens lands right behind
    // cam_lens_d instead of sitting recessed deep in the cavity.
    cam_standoff_h = 4;
    for (x = [-1, 1])
        translate([cam_cx + x * cam_hole_pitch / 2, cam_cy, wall])
            snap_peg(cam_standoff_h, hole_r = cam_hole_d / 2);

    // Display retaining sleeve — see display_sleeve() for why this
    // replaced the old redundant pocket cut. Depth extends a couple
    // mm past the display's own thickness so it's not a hair-trigger
    // fit against disp_h alone.
    display_sleeve(disp_cx, disp_cy, disp_l, disp_w, disp_h + 2, wall, disp_sleeve_clr);

    // Reference only, not part of the printed geometry: transparent
    // outlines of the camera board sitting on its pegs, and the
    // display sitting in its sleeve.
    translate([cam_cx, cam_cy, wall + cam_standoff_h + cam_pcb_h / 2])
        %cube([cam_pcb_l, cam_pcb_w, cam_pcb_h], center = true);
    translate([disp_cx, disp_cy, wall + disp_h / 2])
        %cube([disp_l, disp_w, disp_h], center = true);
}

// ============================================================
// PART 2 — REAR SHELL
// Closed back face: Nano ventilation, one combined cable pass-through
// for the relay wiring and the Nano's power lead, CO2 hopper, and
// standoff-mounted Nano/battery/protoboard — all three bolted flush
// against the INSIDE of this same back wall (footprint in X-Y,
// standing only standoff_h + their own thickness into the box) rather
// than resting on a floor deep inside it. That's what keeps this
// shell around 60mm deep instead of 240mm. Its front mouth recesses
// collar_len deep, constant box_w x box_h cavity, so the front
// shell's collar slides straight in. Print open-mouth down, no
// supports needed for the vent holes or the hopper's open top.
// ============================================================
module rear_shell() {
    inner_w = box_w - 2 * wall;
    inner_h = box_h - 2 * wall;

    // CO2 hopper: ONE gravity-fed magazine mounted flush against the
    // back wall — protrudes only hopper_depth (about one cartridge
    // diameter). Cartridges lie on their sides, long axis along X,
    // loaded from the open top and stacking directly on each other in
    // Y inside a shaft that's enclosed on all sides (co2_hopper()'s
    // back/bottom/ends/front walls) except one open slot at the very
    // bottom — the only place you can actually pull a cartridge out,
    // so removing it drops the whole stack down one position rather
    // than letting you grab from the middle. Positioned at
    // back_cap_inner_z (where the solid cap begins, not the hollow
    // cavity behind it) so the housing's back wall fuses through the
    // full cap thickness — starting at the cap's outer face instead
    // would have had that back wall carved away by the interior
    // cavity cut below before ever reaching solid material.
    hopper_l       = co2_len + 10;                     // cartridge length + clearance
    hopper_stack_h = co2_count * (co2_d + 2) + 10;      // stacked cartridges + small gaps + top loading clearance
    hopper_depth   = co2_d + 2 * wall;
    hopper_slot_h  = wall + co2_d;  // bottom wall thickness + one cartridge, so the front wall starts exactly where the second cartridge does, not partway through the first
    hopper_cx      = 70;  // right portion of the back face

    // Nano + battery mounted side by side in the left two-thirds of
    // the back face (clear of the hopper's x=31..109 footprint);
    // protoboard tucked into the clear space directly above the
    // hopper. Verified pairwise (nano/battery/protoboard/hopper) for
    // zero overlap and staying within box_w x box_h before committing
    // to these numbers — see the conversation, not re-derived here.
    hopper_left_edge = hopper_cx - hopper_l / 2;               // 31
    left_zone_w      = hopper_left_edge - (-box_w / 2);        // 152.95
    nano_cx = -box_w / 2 + left_zone_w / 2;
    batt_cx = nano_cx;
    batt_cy = -box_h / 2 + batt_w / 2 + 5;                     // battery's 71mm edge sets its own height here
    nano_cy = batt_cy + batt_w / 2 + 10 + nano_w / 2;          // stacked directly above the battery, 10mm gap
    pcb_cx  = hopper_cx;
    pcb_cy  = (hopper_stack_h / 2 + box_h / 2) / 2;            // centered in the clear space above the hopper

    difference() {
        union() {
            rounded_box(box_w, box_h, rear_shell_depth, corner_r);
            translate([hopper_cx - hopper_l / 2, -hopper_stack_h / 2, back_cap_inner_z])
                co2_hopper(hopper_l, hopper_stack_h, hopper_depth, wall, hopper_slot_h);
        }

        // Hollow interior, open at the mouth (z=0), stopping short
        // of the back by one wall thickness so a solid cap remains
        // for the vent holes and cable slot to cut into. An earlier
        // draft cut this all the way through both ends, which left
        // no back cap at all.
        translate([0, 0, -0.1])
            linear_extrude(back_cap_inner_z + 0.1)
                hull()
                    for (x = [-1, 1], y = [-1, 1])
                        translate([x * (inner_w / 2 - corner_r),
                                   y * (inner_h / 2 - corner_r)])
                            circle(r = corner_r);

        // Snap dimples matching front_shell()'s bumps. Measured from
        // THIS shell's own mouth (z=0): the collar's tip lands
        // collar_len inside once fully seated, and the bump sits 4mm
        // short of that tip — so the dimple belongs at collar_len-4
        // from the mouth, not from the back cap. (An earlier draft
        // had this measured from the wrong end entirely.)
        for (side = [-1, 1])
            translate([side * (inner_w / 2), 0, collar_len - 4])
                rotate([0, side > 0 ? 90 : -90, 0])
                    snap_dimple();

        // Back-face ventilation grid, cut through the back cap
        // (Z from back_cap_inner_z to rear_shell_depth), directly
        // behind the Nano's own new position. The four outermost
        // corners are skipped: at 6 rows, they land close enough to
        // the Nano's own mounting pegs (inset 8mm from the board's
        // corners) to cut into a peg's base — checked by measuring
        // peg-to-hole distance, not eyeballed.
        for (xf = [-2, -1, 0, 1, 2], yf = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5])
            if (!(abs(xf) == 2 && abs(yf) == 2.5))
                translate([nano_cx + xf * (nano_l / 5), nano_cy + yf * (nano_w / 6),
                           back_cap_inner_z - 0.1])
                    cylinder(h = wall + 0.2, r = 3);

        // Combined cable pass-through, also through the back cap:
        // relay/solenoid wiring and the Nano's own power-barrel lead
        // exit here. Positioned in the one large area nothing else
        // occupies — below the hopper, right of the Nano/battery
        // column — rather than fighting for space near the boards.
        translate([hopper_cx, -box_h / 2 + (box_h / 2 - hopper_stack_h / 2) / 2,
                   back_cap_inner_z - 0.1])
            linear_extrude(wall + 0.2)
                hull()
                    for (x = [-1, 1])
                        translate([x * 8, 0])
                            circle(r = 6);
    }

    // Mounted boards: added AFTER the difference() above (a sibling
    // statement, implicitly unioned with it) rather than inside it —
    // geometry positioned this close to the back cap would otherwise
    // fall inside the interior-cavity cut and get removed by it
    // before ever printing. Nano and the protoboard both plausibly
    // have real mounting holes, so they get snap pegs (secures them
    // in every direction, including against gravity); the battery has
    // none, so it gets an actual shelf to rest on instead — a peg
    // pattern would be pure guesswork there with nothing to secure it
    // to. Peg/post positions are still generic placeholders, not
    // matched to any board's real hole pattern.
    wall_snap_pegs(nano_cx, nano_cy, nano_l, nano_w, back_cap_inner_z, standoff_h);
    wall_snap_pegs(pcb_cx, pcb_cy, pcb_l, pcb_w, back_cap_inner_z, standoff_h, inset = 6);
    wall_shelf(batt_cx, batt_cy - batt_w / 2, batt_l, standoff_h + batt_h, back_cap_inner_z, wall, lip_h = 12);

    // Reference only, not part of the printed geometry: transparent
    // (OpenSCAD's % modifier, auto-excluded from F6/render and STL)
    // outlines of the Nano, battery, and protoboard sitting on their
    // standoffs, plus co2_count cartridges in the hopper — so you can
    // actually see the layout instead of reading bare posts and an
    // empty hopper shell.
    translate([nano_cx, nano_cy, back_cap_inner_z - standoff_h - nano_h / 2])
        %cube([nano_l, nano_w, nano_h], center = true);
    translate([batt_cx, batt_cy, back_cap_inner_z - standoff_h - batt_h / 2])
        %cube([batt_l, batt_w, batt_h], center = true);
    translate([pcb_cx, pcb_cy, back_cap_inner_z - standoff_h - pcb_thickness / 2])
        %cube([pcb_l, pcb_w, pcb_thickness], center = true);
    for (i = [0 : co2_count - 1])
        translate([hopper_cx,
                   -hopper_stack_h / 2 + wall + co2_d / 2 + i * co2_d,
                   back_cap_inner_z + wall + co2_d / 2])
            rotate([0, 90, 0])
                %cylinder(h = co2_len, r = co2_d / 2, center = true, $fn = 24);
}

// ============================================================
// RENDER
// ============================================================
if (render_front_shell) front_shell();
if (render_rear_shell)  rear_shell();

// Assembled preview: rear shell fixed at its own origin (mouth at
// z=0, back cap at z=rear_shell_depth); front shell's own z=0 (its
// face) shifted to z=-front_clear_depth so its collar tip lands at
// z=collar_len inside the rear shell — matching where the snap
// dimples were placed above. Fit-check only, not for slicing.
if (render_assembly) {
    rear_shell();
    translate([0, 0, -front_clear_depth])
        front_shell();
}

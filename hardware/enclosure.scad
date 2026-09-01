// ============================================================
// COOK rig enclosure — fastener-free: printed snap-fits and
// dovetail slides only. No screws, inserts, nuts, or glue.
//
// Open in OpenSCAD (openscad.org, free). This is a first-pass
// parametric starting point, not a print-ready file: several
// dimensions below are PLACEHOLDERS marked "MEASURE YOURS" —
// update them from your actual parts, then hit F5 to preview
// before slicing anything.
//
// Print each part as a SEPARATE STL: set exactly one render_*
// flag true, F6 (render), export STL, repeat for the next part.
// Interlocking geometry like this cannot be printed as one piece.
//
// Material note: PETG or ASA for anything with a snap_tab — PLA
// gets brittle under repeated flexing and the lid tabs will
// eventually snap off. Base plate and pipe clips are fine in PLA.
// ============================================================

// ---- WHICH PART TO RENDER ----
// Exactly one render_* true prints that part's own STL, positioned at
// its own origin. render_assembly instead shows all five together,
// each translated to where it actually sits relative to the base
// plate -- for looking at the overall layout, not for slicing (the
// individual, origin-centered renders are what you export per part).
render_base         = true;
render_lid           = false;
render_bezel_front   = false;
render_bezel_rear    = false;
render_solenoid_rail = false;
render_assembly      = false;

// ---- GLOBAL TOLERANCES ----
wall     = 2.4;   // shell wall thickness (~6 perimeters at 0.4mm nozzle)
fit_gap  = 0.25;  // clearance for friction-fit pockets
snap_gap = 0.35;  // clearance around snap tabs so they flex freely
corner_r = 3;     // outer corner rounding
$fn      = 48;    // circle smoothness

// ============================================================
// MEASURE-AND-CONFIRM: component footprints
// Confirmed from spec sheets: display. Everything else is a
// reasonable placeholder — measure your actual part and edit
// before slicing, or the pockets/clips will be wrong.
// ============================================================

// -- Jetson Nano devkit carrier board (B01 devkit, incl. heatsink) --
nano_l = 100; nano_w = 80; nano_h = 30;

// -- Display: Hosyond 7", CONFIRMED from spec sheet --
disp_l = 164.9; disp_w = 102.0; disp_h = 15.15;
disp_active_l = 154.21; disp_active_w = 85.92;

// -- Relay module (PLACEHOLDER — measure yours) --
relay_l = 50; relay_w = 26; relay_h = 19;

// -- Aobao 8xAA battery holder (PLACEHOLDER — measure yours) --
batt_l = 115; batt_w = 55; batt_h = 15;

// -- Pneumatic assembly clip diameters (PLACEHOLDER — measure yours,
//    calipers around the solenoid body / regulator body / barrel) --
solenoid_body_d  = 24;
regulator_body_d = 32;
barrel_d         = 16;

// Shared between base_plate() and electronics_lid(), which are
// rendered and printed separately — this is what keeps the lid's
// snap tabs landing on the base's snap slots despite the two
// modules never sharing a coordinate system at print time.
lid_zone_len = nano_l + batt_l + 24;
lid_tab_xf   = [-0.3, 0, 0.3];  // fractional positions along lid_zone_len

// Base plate layout, lifted out of base_plate() to file scope so
// render_assembly (bottom of file) can position the other four parts
// against the exact same numbers instead of a second, driftable copy.
plate_l = disp_l + nano_l + batt_l + 40;
plate_w = max(disp_w, nano_w + batt_w + 20) + 20;
plate_h = 4;

disp_zone_x  = -plate_l / 2 + disp_l / 2 + 10;
nano_zone_x  = disp_zone_x + disp_l / 2 + 10 + nano_l / 2;
batt_zone_x  = nano_zone_x + nano_l / 2 + 10 + batt_l / 2;
rail_zone_x  = plate_l / 2 - 30;  // matches base_plate()'s solenoid dovetail rail

// ============================================================
// BUILDING BLOCKS — the fastener-free mechanisms
// ============================================================

// Rounded rectangular box, solid, extruded up from z=0.
module rounded_box(l, w, h, r) {
    linear_extrude(h)
        hull()
            for (x = [-1, 1], y = [-1, 1])
                translate([x * (l / 2 - r), y * (w / 2 - r)])
                    circle(r = r);
}

// Cantilever snap tab: thin flexible root + a lip that catches past
// the far face of whatever wall it's pushed through. Attach at the
// XY origin, tab extends in +Z, flexes in X.
module snap_tab(len = 8, width = 6, thick = 1.6, lip = 1.2) {
    union() {
        cube([thick, width, len]);
        translate([thick, 0, len - 3])
            cube([lip, width, 3]);
    }
}

// Matching through-slot to cut into a mating wall with difference().
// Make the wall at least (thick + lip) deep so the lip has somewhere
// to catch once it springs back on the far side.
module snap_slot(len = 8, width = 6, thick = 1.6, lip = 1.2, clr = snap_gap) {
    translate([-clr / 2, -clr / 2, -0.1])
        cube([thick + lip + clr, width + clr, len + clr + 0.2]);
}

// Dovetail rail, male, centered on and running along Y, protruding
// +height in Z from wherever it's translated to. Sub-assemblies
// slide on lengthwise (along Y) and are retained by the trapezoid
// cross-section. A single-axis rotation on a centered extrusion —
// deliberately simple so the orientation is easy to hand-verify;
// an earlier compound rotate([90,0,90]) here was wrong (it put the
// "sticks up" dimension sideways instead of in Z) and I caught that
// by tracing the matrices, not by rendering — I don't have OpenSCAD
// available to confirm this in the sandbox, so check the preview.
module dovetail_male(length, base_w = 10, top_w = 6, height = 4) {
    rotate([90, 0, 0])
        linear_extrude(length, center = true)
            polygon([
                [-base_w / 2, 0], [base_w / 2, 0],
                [top_w / 2, height], [-top_w / 2, height],
            ]);
}

// Matching female channel, cut with difference(). Same orientation
// convention as dovetail_male().
module dovetail_female(length, base_w = 10, top_w = 6, height = 4, clr = fit_gap) {
    translate([0, 0, -0.1])
        rotate([90, 0, 0])
            linear_extrude(length + 0.4, center = true)
                offset(clr)
                    polygon([
                        [-base_w / 2, 0], [base_w / 2, 0],
                        [top_w / 2, height], [-top_w / 2, height],
                    ]);
}

// Printed C-clip cradle for a cylindrical part (solenoid body,
// regulator body, barrel). The opening is narrower than the part's
// diameter — the printed ring flexes open on insertion and the
// plastic's spring-back holds it afterward, no strap or fastener.
// Mount by placing this module's origin where you want the pipe's
// centerline; it stands on a small foot below z=0.
module pipe_clip(d, gap_w = 8, wall_t = 3, squeeze = 0.6, depth = 10,
                  stand_h = 14, stand_w = 20) {
    r = d / 2;
    difference() {
        union() {
            cylinder(h = depth, r = r + wall_t);
            translate([-stand_w / 2, -3, -stand_h])
                cube([stand_w, 6, stand_h]);
        }
        translate([0, 0, -0.1])
            cylinder(h = depth + 0.2, r = r - squeeze / 2);
        // Opening, facing +Y (up) for easy top-loading insertion.
        translate([-gap_w / 2, 0, -1])
            cube([gap_w, r + wall_t + 1, depth + 2]);
    }
}

// ============================================================
// PART 1 — BASE PLATE
// Everything else slides onto its dovetail rails and locks, or
// sits in a friction-fit pocket. Print flat, no supports.
// ============================================================
module base_plate() {
    difference() {
        union() {
            rounded_box(plate_l, plate_w, plate_h, corner_r);

            // Dovetail rail for the display bezel's foot.
            translate([disp_zone_x, 0, plate_h])
                dovetail_male(disp_w - 10, base_w = 10, top_w = 6, height = 4);

            // Dovetail rail for the solenoid rail sub-assembly, at
            // the far end past the battery bay.
            translate([rail_zone_x, 0, plate_h])
                dovetail_male(plate_w - 30, base_w = 10, top_w = 6, height = 4);

            // Snap-slot side walls the electronics lid clips onto,
            // running the length of the Nano + relay + battery zone.
            // lid_zone_len is shared with electronics_lid() (see top
            // of file) so the tabs land on these walls.
            lid_zone_x0 = nano_zone_x - lid_zone_len / 2;
            translate([lid_zone_x0, -(nano_w / 2) - wall, plate_h])
                cube([lid_zone_len, wall, 12]);
            translate([lid_zone_x0, nano_w / 2, plate_h])
                cube([lid_zone_len, wall, 12]);
        }

        // Slots matching electronics_lid()'s snap tabs: same
        // translate/rotate pattern as that module's tab placement,
        // just against snap_slot() instead of snap_tab(), and
        // shifted up by plate_h since this wall sits on top of the
        // plate. Nudge the Y offset in the OpenSCAD preview if the
        // lip doesn't land cleanly on the wall's far face — I
        // couldn't render this file to confirm the fit myself.
        for (side = [-1, 1])
            for (xf = lid_tab_xf)
                translate([nano_zone_x + xf * lid_zone_len,
                           side * ((nano_w / 2) + wall / 2),
                           plate_h])
                    rotate([0, 0, side > 0 ? 0 : 180])
                        snap_slot();

        // Nano board recess — friction-fit pocket, board drops in
        // and rests on the pocket floor (add corner support bosses
        // matched to your board's mount-hole spacing if you want it
        // properly captured rather than just resting).
        translate([nano_zone_x, 0, plate_h - 1.6])
            rounded_box(nano_l + fit_gap, nano_w + fit_gap, 2, 2);

        // Relay recess, alongside the Nano.
        translate([nano_zone_x, nano_w / 2 + relay_w / 2 + 4, plate_h - 1.6])
            rounded_box(relay_l + fit_gap, relay_w + fit_gap, 2, 2);

        // Battery holder channel.
        translate([batt_zone_x, 0, plate_h - 1.6])
            rounded_box(batt_l + fit_gap, batt_w + fit_gap, 2, 2);

        // Cable pass-through slots between bays (CSI ribbon, wiring).
        translate([disp_zone_x + disp_l / 2 + 5, 0, 0])
            cube([6, 20, plate_h + 2], center = true);
        translate([nano_zone_x + nano_l / 2 + 5, 0, 0])
            cube([6, 20, plate_h + 2], center = true);
    }

    // Printed feet — truncated cones, no rubber pads needed.
    for (x = [-plate_l / 2 + 15, plate_l / 2 - 15])
        for (y = [-plate_w / 2 + 15, plate_w / 2 - 15])
            translate([x, y, -3])
                cylinder(h = 3, r1 = 6, r2 = 4);
}

// ============================================================
// PART 2 — ELECTRONICS LID
// Clips over the Nano + relay + battery zone via snap tabs that
// hook into the base plate's side walls. Leaves the display and
// solenoid-rail dovetail zones uncovered (they're their own
// sub-assemblies). Print with the flat side down, no supports.
// ============================================================
module electronics_lid() {
    // lid_l intentionally equals the shared lid_zone_len (see top of
    // file) so these tabs land on base_plate()'s matching slots.
    lid_l = lid_zone_len;
    lid_w = nano_w + 2 * (wall + 6);
    lid_h = nano_h + 6;

    difference() {
        union() {
            translate([0, 0, lid_h / 2])
                difference() {
                    rounded_box(lid_l, lid_w, lid_h, corner_r);
                    translate([0, 0, wall])
                        rounded_box(lid_l - 2 * wall, lid_w - 2 * wall, lid_h, 2);
                }

            // Snap tabs on both long edges, same xf fractions and
            // count as the slots cut in base_plate().
            for (side = [-1, 1])
                for (xf = lid_tab_xf)
                    translate([xf * lid_l, side * (lid_w / 2 - wall / 2), 0])
                        rotate([0, 0, side > 0 ? 0 : 180])
                            snap_tab();
        }

        // Ventilation slots over the Nano's heatsink — do not
        // enclose this without airflow.
        for (xf = [-0.25, 0, 0.25])
            translate([xf * lid_l, 0, lid_h + 2])
                cube([8, lid_w - 20, 6], center = true);

        // Port cutouts: tune position/size to your board's actual
        // connector placement before printing. Placeholder shown
        // for one side (HDMI/USB/power edge).
        translate([-lid_l / 2, 0, lid_h / 2])
            cube([4, 40, 20], center = true);
    }
}

// ============================================================
// PART 3 — DISPLAY BEZEL (front + rear, sandwich the panel edge)
// Front and rear halves snap together with the display's lip
// trapped between them — no screws through the glass bezel.
// The rear half carries the dovetail foot that slides onto the
// base plate.
// ============================================================
module display_bezel_front() {
    difference() {
        rounded_box(disp_l + 2 * wall, disp_w + 2 * wall, 6, corner_r);
        translate([0, 0, 1.5])
            rounded_box(disp_active_l, disp_active_w, 6, 2);
        translate([0, 0, -0.1])
            rounded_box(disp_l - 4, disp_w - 4, 3, corner_r - 1);
    }
    // Snap pins that mate into the rear half's sockets.
    for (x = [-1, 1], y = [-1, 1])
        translate([x * (disp_l / 2 - 8), y * (disp_w / 2 - 8), -4])
            cylinder(h = 4.5, r = 2.2);
}

module display_bezel_rear() {
    difference() {
        rounded_box(disp_l + 2 * wall, disp_w + 2 * wall, 8, corner_r);
        translate([0, 0, wall])
            rounded_box(disp_l - 4, disp_w - 4, 8, corner_r - 1);
        // Snap sockets matching the front half's pins.
        for (x = [-1, 1], y = [-1, 1])
            translate([x * (disp_l / 2 - 8), y * (disp_w / 2 - 8), 3.5])
                cylinder(h = 5, r = 2.4 + fit_gap);
        // Dovetail socket (female) — base_plate()'s rail is male, so
        // this side has to be the channel that receives it, not
        // another male foot. Cut into the bottom face.
        translate([0, 0, 0.1])
            dovetail_female(disp_w - 10, base_w = 10, top_w = 6, height = 4);
    }
}

// ============================================================
// PART 4 — SOLENOID / PNEUMATIC RAIL
// Deliberately NOT a closed enclosure: the regulator gauge needs
// to stay visible and readable, and the solenoid coil needs
// airflow (a held-on coil overheats — see docs/wiring.md). This
// is an open rail of C-clips, dovetailed onto the base plate.
// ============================================================
module solenoid_rail() {
    rail_l = 140;
    difference() {
        rounded_box(rail_l, 30, 4, 2);
        translate([0, 0, -0.1])
            dovetail_female(rail_l, base_w = 10, top_w = 6, height = 4);
    }
    translate([-rail_l / 2 + 25, 0, 4])
        pipe_clip(solenoid_body_d, gap_w = solenoid_body_d * 0.55);
    translate([0, 0, 4])
        pipe_clip(regulator_body_d, gap_w = regulator_body_d * 0.55);
    translate([rail_l / 2 - 20, 0, 4])
        pipe_clip(barrel_d, gap_w = barrel_d * 0.6);
}

// ============================================================
// RENDER
// ============================================================
if (render_base)         base_plate();
if (render_lid)           electronics_lid();
if (render_bezel_front)   display_bezel_front();
if (render_bezel_rear)    display_bezel_rear();
if (render_solenoid_rail) solenoid_rail();

// Assembled layout preview -- positions the other four parts against
// base_plate()'s own zone math (disp_zone_x / nano_zone_x / rail_zone_x
// / plate_h), so the X/Y placement should be trustworthy. The bezel
// front's Z stack-height (8) is read off display_bezel_rear()'s body
// height, not measured from a real fit -- like the rest of this file,
// I don't have OpenSCAD to render and confirm it, so treat this as
// "does the overall layout make sense," not a verified assembly.
if (render_assembly) {
    base_plate();
    translate([nano_zone_x, 0, plate_h])
        electronics_lid();
    translate([disp_zone_x, 0, plate_h])
        display_bezel_rear();
    translate([disp_zone_x, 0, plate_h + 8])
        display_bezel_front();
    translate([rail_zone_x, 0, plate_h])
        solenoid_rail();
}

// fetch these repos from https://github.com/openscad
// and put them into the folder shown by File --> Show Library Folder...
use <scad-utils/transformations.scad>
use <scad-utils/shapes.scad>
use <list-comprehension-demos/skin.scad>

$fn=80;

// units are mm
// schedule 40 1.5 inch pipe is OD=1.900 in., ID=1.610 in.
// schedule 40 4   inch pipe is OD=4.500 in., ID=4.026 in.
// fan shroud OD=~96mm

tube1_od_fudge = 0.0;
tube1_d_extra = 24;  // additional outer wall diameter at the end of tube
tube1_id = 96;
tube1_od = 96 + tube1_od_fudge;
tube1_ed = tube1_od+tube1_d_extra;
tube1_coverage = 30;

// for SCH40 1.5in from wall
tube2_od_fudge = 0.5;
tube2_d_extra = 20;  // additional outer wall diameter at the end of tube
tube2_id = 1.610*25.4;
tube2_od = 1.900*25.4 + tube2_od_fudge;
tube2_ed = tube2_od+tube2_d_extra;
tube2_coverage = 20;

height_from_deck=20;
pipe_pipe_shift=tube1_ed/2-tube2_od/2-height_from_deck;

// for SCH40 4in for exhaust
//tube2_od_fudge = 0.5;
//tube2_d_extra = 20;  // additional outer wall diameter at the end of tube
//tube2_id = 4.026*25.4;
//tube2_od = 4.500*25.4 + tube2_od_fudge;
//tube2_ed = tube2_od+tube2_d_extra;
//tube2_coverage = 20;
//
//pipe_pipe_shift=7;

pipe_pipe_transition=40;  // smoothing/adapting length

difference(){
    skin([
        transform(translation([0,0,0]), circle(r=tube1_od/2)),
        transform(translation([0,0,tube1_coverage]), circle(r=(tube1_ed)/2)),
        transform(translation([0,pipe_pipe_shift,tube1_coverage+pipe_pipe_transition]), circle(r=(tube2_ed)/2)),
        transform(translation([0,pipe_pipe_shift,tube1_coverage+pipe_pipe_transition+tube2_coverage]), circle(r=tube2_od/2))
    ]);
    skin([
        transform(translation([0,0,0]), circle(r=tube1_od/2)),
        transform(translation([0,0,tube1_coverage]), circle(r=tube1_od/2)),
        transform(translation([0,0,tube1_coverage]), circle(r=tube1_id/2)),
        transform(translation([0,pipe_pipe_shift,tube1_coverage+pipe_pipe_transition]), circle(r=tube2_id/2)),
        transform(translation([0,pipe_pipe_shift,tube1_coverage+pipe_pipe_transition]), circle(r=tube2_od/2)),
        transform(translation([0,pipe_pipe_shift,tube1_coverage+pipe_pipe_transition+tube2_coverage]), circle(r=tube2_od/2))
    ]);
}
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

d_over_fan_max = 120;
d_over_fan_min = 96;
l_below = 30;

tube2_id = 1.610*25.4;
tube2_od = 1.9*25.4;
tube2_od_fudge = 0.5;
tube2_d_extra = 20;  // additional outer wall diameter at the end of tube2
tube2_coverage = 20;

pipe_pipe_transition=40;
height_from_deck=20;
pipe_pipe_shift=d_over_fan_max/2-tube2_od/2-height_from_deck;
//pipe_pipe_shift = 0;

difference(){
    skin([
        transform(translation([0,0,-l_below]), circle(r=d_over_fan_min/2)),
        transform(translation([0,0,0]), circle(r=d_over_fan_max/2)),
        transform(translation([0,pipe_pipe_shift,pipe_pipe_transition+tube2_coverage]), circle(r=(tube2_od+tube2_od_fudge)/2))
    ]);
    skin([
        transform(translation([0,0,-l_below]), circle(r=d_over_fan_min/2)),
        transform(translation([0,0,0]), circle(r=d_over_fan_min/2)),
        transform(translation([0,pipe_pipe_shift,pipe_pipe_transition]), circle(r=tube2_id/2)),
        transform(translation([0,pipe_pipe_shift,pipe_pipe_transition]), circle(r=(tube2_od+tube2_od_fudge)/2)),
        transform(translation([0,pipe_pipe_shift,pipe_pipe_transition+tube2_coverage]), circle(r=(tube2_od+tube2_od_fudge)/2))
    ]);
}
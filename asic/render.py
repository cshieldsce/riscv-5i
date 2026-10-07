# render.py: Render the final GDS with KLayout for the README.
#
# Usage (the LibreLane container already has KLayout):
#   klayout -z -nc -rx -r render.py \
#       -rd gds=runs/<run>/final/gds/PipelinedCPU.gds \
#       -rd lyp=<pdk root>/sky130A/libs.tech/klayout/tech/sky130A.lyp \
#       -rd out=results
#
# Drawing every layer at once just gives a solid magenta square, so each image
# only turns on the layers worth looking at.

import os

import pya

# gds, lyp and out come from -rd on the command line

# Sky130 GDS layer/datatype numbers
DIFF = (65, 20)
POLY = (66, 20)
LICON = (66, 44)
LI1 = (67, 20)
MCON = (67, 44)
MET2 = (69, 20)
MET3 = (70, 20)
MET4 = (71, 20)
MET5 = (72, 20)

view = pya.LayoutView()
view.load_layout(gds, 0)
view.load_layer_props(lyp)
view.max_hier()
view.set_config("background-color", "#0d0d10")
view.set_config("grid-visible", "false")
view.set_config("text-visible", "false")
view.set_config("cell-box-visible", "false")


def show_only(layers):
    it = view.begin_layers()
    while not it.at_end():
        props = it.current()
        # Group entries in the .lyp have children, leave those alone
        if not props.has_children():
            new_props = props.dup()
            new_props.visible = (props.source_layer, props.source_datatype) in layers
            view.set_layer_properties(it, new_props)
        it.next()


def save(name, layers, size, box=None):
    show_only(layers)
    if box is None:
        view.zoom_fit()
    else:
        view.zoom_box(box)
    view.save_image(os.path.join(out, name), size, size)
    print(f"Wrote {name}")


# 1. The whole block with routing layers only. met1 covers everything under
# it, so it stays off.
save("layout.png", [MET2, MET3, MET4, MET5], 1000)

# 2. A 20 x 20 um window in the middle to show the standard cells themselves
save("cells.png", [DIFF, POLY, LI1, LICON, MCON], 800, pya.DBox(240, 245, 260, 265))

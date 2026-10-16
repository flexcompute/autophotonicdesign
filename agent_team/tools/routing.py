"""Routing helpers that keep LVS correct.

PhotonForge 2.0 LVS treats a component whose `parametric_function` starts with
'photonforge.parametric.route' as ONE wire and joins all its ports into one net. A multi-net
`pf.parametric.route_auto` call returns all nets in one such component, so LVS merges the nets.
The nets inside it (one child per net) carry no `parametric_function`.

`add_routes` adds each net as its own tagged wire. Route all nets in ONE `route_auto` call (it
avoids collisions between them), then add the result with `add_routes`.
"""

import photonforge as pf


def add_routes(chip: pf.Component, bundle: pf.Component) -> list[pf.Reference]:
    """Add a `route_auto` result to `chip` as one LVS wire per net. Returns the new references."""
    refs = []
    for ref in bundle.references:
        ref.component.parametric_function = "photonforge.parametric.route_auto"
        refs.append(chip.add_reference(pf.Reference(
            ref.component, origin=tuple(ref.origin), rotation=ref.rotation, x_reflection=ref.x_reflection)))
    return refs


def route_nets(chip: pf.Component, nets, *, radius: float, obstacles=None, **kwargs) -> list[pf.Reference]:
    """Route `nets` = [((ref, port), (ref, port)), ...] in one `route_auto` call and add them LVS-safe.

    `obstacles` defaults to every reference already in `chip`. Other keyword arguments go to
    `route_auto` (for example collision_layers, collision_offset, grid_size, search_margin).
    """
    bundle = pf.parametric.route_auto(
        port1=[a for a, _ in nets], port2=[b for _, b in nets], radius=radius,
        obstacles=list(chip.references) if obstacles is None else obstacles,
        show_progress=False, **kwargs)
    return add_routes(chip, bundle)

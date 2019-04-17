"""Test the SedDepEroder component.

Test the sed dep eroder by turning it over a few times. No attempt has been
made to ensure the solution is stable. Takes a topo already output and runs it
a few more times, to ensure repeatability.
"""
import os

import numpy as np
import os
from numpy.testing import assert_array_almost_equal, assert_equal
from six.moves import range

from landlab import RasterModelGrid, CLOSED_BOUNDARY, ModelParameterDictionary
from landlab.components import FlowAccumulator
from landlab.components import SedDepEroder
from landlab.components import FastscapeEroder

from landlab.components.stream_power.cfuncs import (
    sed_flux_fn_gen_genhump, sed_flux_fn_gen_lindecl,
    sed_flux_fn_gen_almostparabolic, sed_flux_fn_gen_const,
    get_sed_flux_function_pseudoimplicit_bysedout
)


def test_flux_fn_const():
    """
    Tests that the const function always returns 1.
    """
    fnval = sed_flux_fn_gen_const(0., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 1.)
    fnval = sed_flux_fn_gen_const(1., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 1.)
    fnval = sed_flux_fn_gen_const(2., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 1.)


def test_flux_fn_lindecl():
    """
    Tests that the linear decline function returns correct values.
    """
    fnval = sed_flux_fn_gen_lindecl(0., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 1.)
    fnval = sed_flux_fn_gen_lindecl(1., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 0.)
    fnval = sed_flux_fn_gen_lindecl(
        0.5, np.nan, np.nan, np.nan, np.nan, np.nan
    )
    assert np.isclose(fnval, 0.5)
    # observe we permit undefined vals
    fnval = sed_flux_fn_gen_lindecl(2., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, -1.)


def test_flux_fn_almostpara():
    """
    Tests that the almost parabolic function returns correct values.
    """
    fnval = sed_flux_fn_gen_almostparabolic(
        0., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 0.1)
    fnval = sed_flux_fn_gen_almostparabolic(
        0.5, np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 1.)
    fnval = sed_flux_fn_gen_almostparabolic(
        1., np.nan, np.nan, np.nan, np.nan, np.nan)
    assert np.isclose(fnval, 0.)


def test_flux_fn_genhump():
    """
    Tests that the generalized function returns correct values.
    """
    fnval = sed_flux_fn_gen_genhump(
        0., 13.683, 1.13, 0.00181, 4.24, 1.0000278041373)
    # remember, phi & c are the weird way round
    assert np.isclose(fnval, 0.024766918603659326)
    fnval = sed_flux_fn_gen_genhump(
        1., 13.683, 1.13, 0.00181, 4.24, 1.0000278041373)
    assert np.isclose(fnval, 0.1975013921257844)
    max_val = 0.
    peak_at = np.nan
    for i in np.arange(0., 1.001, 0.001):
        sff = sed_flux_fn_gen_genhump(
            i, 13.683, 1.13, 0.00181, 4.24, 1.0000278041373)
        if sff > max_val:
            max_val = max((sff, max_val))
            peak_at = i
    assert np.isclose(max_val, 1.)
    assert np.isclose(peak_at, 0.264)
    # finally, check the behaviour at high rel sed fluxes
    fnval = sed_flux_fn_gen_genhump(
        1.e6, 13.683, 1.13, 0.00181, 4.24, 1.0000278041373)
    assert np.isclose(fnval, 0.)
    fnval = sed_flux_fn_gen_genhump(
        2., 13.683, 1.13, 0.00181, 4.24, 1.0000278041373)
    assert np.isclose(fnval, 0.006221557384902739)
    # ^note that the function continues to evolve at RSF>1


def test_set_sed_flux_fn_gen():
    """
    This tests the setter for the sff.
    """
    mg = RasterModelGrid((5, 5))
    z = mg.add_zeros('node', 'topographic__elevation')
    pop_me = set([name for name in SedDepEroder.output_var_names])
    pop_me.discard('topographic__elevation')

    fr = FlowAccumulator(mg, flow_director='D8')
    sde = SedDepEroder(mg, K_sp=1.e-4, sed_dependency_type='None',
                       Qc='power_law', K_t=1.e-4)
    sde._sed_flux_fn_gen is sed_flux_fn_gen_const
    for pop in pop_me:
        null = mg.at_node.pop(pop)
    sde = SedDepEroder(mg, K_sp=1.e-4, sed_dependency_type='linear_decline',
                       Qc='power_law', K_t=1.e-4)
    sde._sed_flux_fn_gen is sed_flux_fn_gen_lindecl
    for pop in pop_me:
        null = mg.at_node.pop(pop)
    sde = SedDepEroder(mg, K_sp=1.e-4, sed_dependency_type='almost_parabolic',
                       Qc='power_law', K_t=1.e-4)
    sde._sed_flux_fn_gen is sed_flux_fn_gen_almostparabolic
    for pop in pop_me:
        null = mg.at_node.pop(pop)
    sde = SedDepEroder(
        mg, K_sp=1.e-4, sed_dependency_type='generalized_humped',
        Qc='power_law', phi_hump=4., K_t=1.e-4
    )
    sde._sed_flux_fn_gen is sed_flux_fn_gen_genhump
    # ...& add a test that the auto-normalization is working OK...
    max_val_comp = 0.
    peak_at_comp = np.nan
    for i in np.arange(0., 1.001, 0.001):
        sff = sed_flux_fn_gen_genhump(
            i, 13.683, 1.13, 0.00181, 4., 1./1.0674809986373335)
        compval = sde._sed_flux_fn_gen(
            i, sde.kappa, sde.nu, sde.c, sde.phi, sde.norm
        )
        assert np.isclose(sff, compval)
        if sff > max_val_comp:
            max_val_comp = max((sff, max_val_comp))
            peak_at = i
    assert np.isclose(max_val_comp, 1.)
    assert np.isclose(peak_at, 0.28)


def test_sff_convergence():
    """
    This tests the stable convergence of the sffs.

    get_sed_flux_function_pseudoimplicit(
        sed_in_bydt,
        trans_cap_vol_out_bydt,
        prefactor_for_volume_bydt,
        prefactor_for_dz_bydt,
        sed_flux_fn_gen,
        kappa, nu, c, phi, norm,
        pseudoimplicit_repeats,
        out_array
    )
    """
    humpk = 13.683
    humpnu = 1.13
    humpc = 0.00181
    humpphi = 4.24
    humpnorm = 1.0000278041373
    models = ('linear_decline', )
    funcs = (sed_flux_fn_gen_lindecl, )
    for (sff_style, solver) in zip(models, funcs):
        mg = RasterModelGrid((5, 5))
        out_array = np.empty(4, dtype=float)
        sde = SedDepEroder(mg, sed_dependency_type=sff_style)
        # special case
        get_sed_flux_function_pseudoimplicit_bysedout(1000., 0., 1., 1.,
                                                      sde._sed_flux_fn_gen,
                                                      humpk, humpnu,
                                                      humpc, humpphi,
                                                      humpnorm,
                                                      50, out_array)
        assert np.isclose(out_array[0], 0.)  # dzbydt
        assert np.isclose(out_array[1], 0.)  # vol_pass_rate
        assert np.isclose(out_array[2], 1.)  # rel_sed_flux
        assert np.isclose(out_array[3], 0.)  # error_in_sed_flux_fn

        # very high flux in. Cell area is 10.
        get_sed_flux_function_pseudoimplicit_bysedout(1.e10, 1., 10., 10.,
                                                      sde._sed_flux_fn_gen,
                                                      humpk, humpnu,
                                                      humpc, humpphi,
                                                      humpnorm,
                                                      50, out_array)
        known_fqs = solver(
            1., humpk, humpnu, humpc, humpphi, humpnorm,
        )
        # Note that this test demonstrates that the range of relative sediment
        # flux is limited to 0. <= qs/qc <= 1.
        assert np.isclose(out_array[0], known_fqs)  # dzbydt
        assert np.isclose(out_array[1], 1.)  # vol_pass_rate
        assert np.isclose(out_array[2], 1.)  # rel_sed_flux
        assert np.isclose(out_array[3], 1.)  # error_in_sed_flux_fn

        # zero flux in. Cell area is 10.
        get_sed_flux_function_pseudoimplicit_bysedout(0., 1.e10, 10., 10.,
                                                      sde._sed_flux_fn_gen,
                                                      humpk, humpnu,
                                                      humpc, humpphi,
                                                      humpnorm,
                                                      50, out_array)
        known_fqs = solver(
            0., humpk, humpnu, humpc, humpphi, humpnorm,
        )
        assert np.isclose(out_array[0], known_fqs*1., atol=0.001)  # dzbydt
        assert np.isclose(out_array[1], known_fqs*10., atol=0.001)
        # ^vol_pass_rate
        assert np.isclose(out_array[2], 0., atol=0.001)  # rel_sed_flux
        assert np.less(out_array[3], 0.001)  # error_in_sed_flux_fn

        # very low flux in. Cell area is 100 and erosion rate is 2.
        get_sed_flux_function_pseudoimplicit_bysedout(1., 1.e10, 200., 100.,
                                                      sde._sed_flux_fn_gen,
                                                      humpk, humpnu,
                                                      humpc, humpphi,
                                                      humpnorm,
                                                      50, out_array)
        known_fqs = solver(
            0., humpk, humpnu, humpc, humpphi, humpnorm,
        )
        assert np.isclose(out_array[0], known_fqs*2., atol=0.001)  # dzbydt
        assert np.isclose(out_array[1], known_fqs*200.+1., atol=0.001)
        # ^vol_pass_rate
        assert np.isclose(out_array[2], 0., atol=0.001)  # rel_sed_flux
        assert np.less(out_array[3], 0.001)  # error_in_sed_flux_fn

        # and a test where we produce a middling qs/qc but enough sed to
        # swamp the outlet
        get_sed_flux_function_pseudoimplicit_bysedout(1., 2., 2000., 2.,
                                                      sde._sed_flux_fn_gen,
                                                      humpk, humpnu,
                                                      humpc, humpphi,
                                                      humpnorm,
                                                      50, out_array)
        assert np.isclose(out_array[2], 0.75, atol=0.001)
        # ^mean of 1./2. (in) and 1 (out)
        known_fqs = solver(
            0.75, humpk, humpnu, humpc, humpphi, humpnorm,
        )
        assert np.isclose(out_array[1], 2., atol=0.001)  # output saturates
        assert np.isclose(out_array[0], (2. - 1.)/2., atol=0.001)
        # ^note this is now controlled by export limit, not fqs directly
        assert np.less(out_array[3], 0.001)  # error_in_sed_flux_fn

    # Now a few specific tests for each form

    # this case represents a direct implicit hit on qs/qc = fqsqc = 0.5 for
    # the linear decline model!
    mg = RasterModelGrid((5, 5))
    out_array = np.empty(4, dtype=float)
    sde = SedDepEroder(mg, sed_dependency_type='linear_decline')
    get_sed_flux_function_pseudoimplicit_bysedout(1., 2., 2., 2.,
                                                  sde._sed_flux_fn_gen,
                                                  humpk, humpnu,
                                                  humpc, humpphi,
                                                  humpnorm,
                                                  50, out_array)
    assert np.isclose(out_array[0], 0.5)
    assert np.isclose(out_array[1], 2.)
    assert np.isclose(out_array[2], 0.5)
    # ^1./2. = 0.5, which gives fqsqc = 0.5, supplies 1 unit sediment (A=2),
    # and so this immediately matches the initial conditions
    assert np.isclose(out_array[3], 0.)  # BOOM













# def test_sed_dep_new_almostpara_fullrun():
#     """
#     This tests only the power_law version of the SDE, using the
#     almost_parabolic form of f(Qs).
#     """
#     mg = RasterModelGrid((10, 5), xy_spacing=200.)
#     for edge in (mg.nodes_at_left_edge, mg.nodes_at_top_edge,
#                  mg.nodes_at_right_edge):
#         mg.status_at_node[edge] = CLOSED_BOUNDARY
# 
#     z = mg.add_zeros('node', 'topographic__elevation')
# 
#     fr = FlowAccumulator(mg, flow_director='D8')
#     sde = SedDepEroder(mg, K_sp=1.e-4, sed_dependency_type='almost_parabolic',
#                        Qc='power_law', K_t=1.e-4)
# 
#     z[:] = mg.node_y/10000.
#     z.reshape((10, 5))[:, 2] *= 2.
#     z.reshape((10, 5))[:, 3] *= 2.1
# 
#     initz = z.copy()
# 
#     dt = 100.
#     up = 0.05
# 
#     for i in range(1):
#         fr.run_one_step()
#         sde.run_one_step(dt)
# 
#     assert_array_almost_equal(mg.at_node['channel_sediment__depth'],
#                               np.array([0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.,
#                                         0.,  0.00023431,  0.,  0.,  0.,
#                                         0.,  0.,  0.,  0.,  0.]))
# 
#     assert_array_almost_equal(z - initz, np.array(
#         [0.,  0.,  0.,  0.,  0.,
#          0., -0.00076662, -0.0004,     -0.00118507,  0.,
#          0., -0.00068314, -0.00042426, -0.00110741,  0.,
#          0., -0.00065571, -0.0006,     -0.00102346,  0.,
#          0., -0.00056135, -0.0008,     -0.00093111,  0.,
#          0., -0.00045180, -0.0010,     -0.00078882,  0.,
#          0., -0.00031903, -0.0012,     -0.00071743,  0.,
#          0., -0.00015763, -0.0014,     -0.00057541,  0.,
#          0.,  0.00023431, -0.0016,     -0.00042,     0.,
#          0.,  0.,  0.,  0.,  0.]))
# 
#     assert_equal(len(sde._error_at_abort), 0)  # good convergence at all nodes
# 
# 
# def test_sed_dep_new_genhumped_fullrun():
#     """
#     This tests only the power_law version of the SDE, using the
#     generalized_humped form of f(Qs).
#     """
#     mg = RasterModelGrid((10, 5), xy_spacing=200.)
#     for edge in (mg.nodes_at_left_edge, mg.nodes_at_top_edge,
#                  mg.nodes_at_right_edge):
#         mg.status_at_node[edge] = CLOSED_BOUNDARY
# 
#     z = mg.add_zeros('node', 'topographic__elevation')
# 
#     fr = FlowAccumulator(mg, flow_director='D8')
#     sde = SedDepEroder(mg, K_sp=1.e-4,
#                        sed_dependency_type='generalized_humped',
#                        Qc='power_law', K_t=1.e-4)
# 
#     z[:] = mg.node_y/10000.
#     z.reshape((10, 5))[:, 2] *= 2.
#     z.reshape((10, 5))[:, 3] *= 2.1
# 
#     initz = z.copy()
# 
#     dt = 100.
#     up = 0.05
# 
#     for i in range(1):
#         fr.run_one_step()
#         sde.run_one_step(dt)
# 
#     ans = np.array([0.,  0.,  0.,  0.,  0.,
#                     0.02,  0.01940896,  0.03969863,  0.04112046,  0.02,
#                     0.04,  0.03948890,  0.07968035,  0.08318039,  0.04,
#                     0.06,  0.05951858,  0.11954794,  0.12524486,  0.06,
#                     0.08,  0.07960747,  0.15939726,  0.16731501,  0.08,
#                     0.10,  0.09969946,  0.19924657,  0.20939250,  0.10,
#                     0.12,  0.11979225,  0.23909589,  0.25147973,  0.12,
#                     0.14,  0.13987971,  0.27894520,  0.29357949,  0.14,
#                     0.16,  0.16023431,  0.31879451,  0.33568356,  0.16,
#                     0.18,  0.18,  0.36,  0.378,  0.18])
# 
#     assert_array_almost_equal(z, ans)
# 
# 
# def test_sed_dep_new_lindecl_fullrun():
#     """
#     This tests only the power_law version of the SDE, using the
#     linear_decline form of f(Qs).
#     """
#     mg = RasterModelGrid((10, 5), xy_spacing=200.)
#     for edge in (
#         mg.nodes_at_left_edge, mg.nodes_at_top_edge, mg.nodes_at_right_edge
#     ):
#         mg.status_at_node[edge] = CLOSED_BOUNDARY
# 
#     z = mg.add_zeros("node", "topographic__elevation")
# 
#     fr = FlowAccumulator(mg, flow_director='D8')
#     sde = SedDepEroder(
#         mg,
#         K_sp=1.e-4,
#         sed_dependency_type='linear_decline',
#         Qc='power_law',
#         K_t=1.e-4)
# 
#     z[:] = mg.node_y/10000.
#     z.reshape((10, 5))[:, 2] *= 2.
#     z.reshape((10, 5))[:, 3] *= 2.1
# 
#     initz = z.copy()
# 
#     dt = 100.
#     up = 0.05
# 
#     for i in range(1):
#         fr.run_one_step()
#         sde.run_one_step(dt)
# 
#     ans = np.array([0.,  0.,  0.,  0.,  0.,
#                     0.02,  0.01955879,  0.03980000,  0.04128996,  0.02,
#                     0.04,  0.03961955,  0.07978787,  0.08333878,  0.04,
#                     0.06,  0.05964633,  0.11970000,  0.12539158,  0.06,
#                     0.08,  0.07971138,  0.15960000,  0.16745207,  0.08,
#                     0.10,  0.09978034,  0.19950000,  0.20951474,  0.10,
#                     0.12,  0.11985392,  0.23940000,  0.25158663,  0.12,
#                     0.14,  0.13993079,  0.27930000,  0.29367338,  0.14,
#                     0.16,  0.16023431,  0.31920000,  0.33579000,  0.16,
#                     0.18,  0.18,  0.36,  0.378,  0.18])
# 
#     assert_array_almost_equal(z, ans)
# 
# 
# def test_sed_dep_new_const_fullrun():
#     """
#     This tests only the power_law version of the SDE, using the
#     constant (None) form of f(Qs).
#     """
#     mg = RasterModelGrid((10, 5), xy_spacing=200.)
#     for edge in (
#         mg.nodes_at_left_edge, mg.nodes_at_top_edge, mg.nodes_at_right_edge
#     ):
#         mg.status_at_node[edge] = CLOSED_BOUNDARY
# 
#     z = mg.add_zeros('node', 'topographic__elevation')
# 
#     fr = FlowAccumulator(mg, flow_director='D8')
#     sde = SedDepEroder(
#         mg,
#         K_sp=1.e-4,
#         sed_dependency_type='None',
#         Qc='power_law',
#         K_t=1.e-4
#     )
# 
#     z[:] = mg.node_y/10000.
#     z.reshape((10, 5))[:, 2] *= 2.
#     z.reshape((10, 5))[:, 3] *= 2.1
# 
#     initz = z.copy()
# 
#     dt = 100.
#     up = 0.05
# 
#     for i in range(1):
#         fr.run_one_step()
#         sde.run_one_step(dt)
# 
#     ans = np.array([0.,  0.,  0.,  0.,  0.,
#                     0.02,  0.01922540,  0.03960000,  0.04081206,  0.02,
#                     0.04,  0.03927889,  0.07957574,  0.08288878,  0.04,
#                     0.06,  0.05930718,  0.11940000,  0.12497121,  0.06,
#                     0.08,  0.07936754,  0.15920000,  0.16706085,  0.08,
#                     0.10,  0.09943431,  0.19900000,  0.20916000,  0.10,
#                     0.12,  0.11951010,  0.23880000,  0.25127254,  0.12,
#                     0.14,  0.13960000,  0.27860000,  0.29340603,  0.14,
#                     0.16,  0.16023431,  0.31840000,  0.33558000,  0.16,
#                     0.18,  0.18,  0.36,  0.378,  0.18])
# 
#     assert_array_almost_equal(z, ans)
# 
# 
# def test_sed_dep_w_hillslopes():
#     """
#     This tests only the power_law version of the SDE, with a hillslope input.
#     """
#     mg = RasterModelGrid((10, 5), xy_spacing=200.)
#     for edge in (
#         mg.nodes_at_left_edge, mg.nodes_at_top_edge, mg.nodes_at_right_edge
#     ):
#         mg.status_at_node[edge] = CLOSED_BOUNDARY
# 
#     z = mg.add_zeros('node', 'topographic__elevation')
#     th = mg.add_zeros('node', 'channel_sediment__depth')
#     th[mg.core_nodes] += 0.001
# 
#     fr = FlowAccumulator(mg, flow_director='D8')
#     sde = SedDepEroder(
#         mg,
#         K_sp=1.e-4,
#         sed_dependency_type='almost_parabolic',
#         Qc='power_law',
#         K_t=1.e-4
#     )
# 
#     z[:] = mg.node_y/10000.
#     z.reshape((10, 5))[:, 2] *= 2.
#     z.reshape((10, 5))[:, 3] *= 2.1
# 
#     initz = z.copy()
# 
#     dt = 100.
#     up = 0.05
# 
#     for i in range(1):
#         print(i)
#         fr.run_one_step()
#         sde.run_one_step(dt)
# 
#     # test binding of field occurs correctly:
#     assert th is mg.at_node['channel_sediment__depth']
# 
#     assert_array_almost_equal(
#         mg.at_node['channel_sediment__depth'],
#         np.array([0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
#                   0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
#                   0.00000000e+00,   6.00000000e-04,   0.00000000e+00,
#                   0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
#                   5.75735931e-04,   0.00000000e+00,   0.00000000e+00,
#                   0.00000000e+00,   0.00000000e+00,   4.00000000e-04,
#                   0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
#                   9.28079257e-07,   2.00000000e-04,   0.00000000e+00,
#                   0.00000000e+00,   0.00000000e+00,   4.13904292e-04,
#                   0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
#                   0.00000000e+00,   7.60612309e-04,   0.00000000e+00,
#                   5.55537486e-06,   0.00000000e+00,   0.00000000e+00,
#                   1.16568542e-03,   0.00000000e+00,   2.32060608e-04,
#                   0.00000000e+00,   0.00000000e+00,   1.73431458e-03,
#                   0.00000000e+00,   5.80000000e-04,   0.00000000e+00,
#                   0.00000000e+00,   0.00000000e+00,   0.00000000e+00,
#                   0.00000000e+00,   0.00000000e+00]))
# 
#     assert_array_almost_equal(z, np.array(
#         [0.,  0.,  0.,  0.,  0.,
#          0.02,  0.01877957,  0.0396,      0.04055596,  0.02,
#          0.04,  0.03891440,  0.07957574,  0.08263689,  0.04,
#          0.06,  0.05890177,  0.1194,      0.12472345,  0.06,
#          0.08,  0.07900093,  0.1592,      0.16681590,  0.08,
#          0.10,  0.09941390,  0.1990,      0.20891231,  0.10,
#          0.12,  0.11976061,  0.23863333,  0.25100556,  0.12,
#          0.14,  0.14016569,  0.27831429,  0.29323206,  0.14,
#          0.16,  0.16073431,  0.318025,    0.335580,    0.16,
#          0.18,  0.18,  0.36,  0.378,  0.18]))
# 
#     # good convergence at all nodes
#     assert_equal(len(sde._error_at_abort), 0)

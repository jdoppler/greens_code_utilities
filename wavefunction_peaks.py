#!/usr/bin/env python2.7

import json
import multiprocessing
import numpy as np
import os
from scipy.ndimage.filters import gaussian_filter, uniform_filter
from scipy import stats
import sys

import argh

from ascii_to_numpy import read_ascii_array
from ep.helpers import get_local_peaks
from helper_functions import convert_json_to_cfg

FILE_NAME = "peaks"
PIC_ASCII_YMIN = 0.2375
PIC_ASCII_YMAX = 0.7500
# POT_MIN_CUTOFF = 1.0
POT_CUTOFF_VALUE = -1.0
# INTERPOLATE_XY_EPS = 5e-4
PLOT_FIGSIZE = (200, 100)
PLOT_FIGSIZE_SCALING = 250
PLOT_FONTSIZE = 100
PICKER_TOLERANCE = 5


def on_pick(event):
    """Record (x, y) coordinates at each click and print to file."""
    xmouse, ymouse = event.mouseevent.xdata, event.mouseevent.ydata
    print "x, y:", xmouse, ymouse
    with open(FILE_NAME + '_interactive.dat', 'a') as f:
        f.write('{} {}\n'.format(xmouse, ymouse))


def on_key(event):
    """Quit the interactive session or reset output file based on a keypress event."""
    if event.key in 'q':
        plt.close()
    if event.key in 'r':
        os.mknod(FILE_NAME + '_interactive.dat')


@argh.arg('--mode1', type=str)
@argh.arg('--mode2', type=str)
@argh.arg('--npz-potential', type=str)
@argh.arg('--txt-potential', type=str)
@argh.arg('--write-peaks', type=str)
@argh.arg('--r-nx', type=int)
@argh.arg('--r-ny', type=int)
@argh.arg('--shift', type=str)
@argh.arg('--limits', type=float, nargs='+')
def main(pphw=50, N=2.5, L=100., W=1., sigmax=10., sigmay=1.,
         amplitude=1., r_nx=None, r_ny=None, plot=False,
         pic_ascii=False, write_peaks=None, mode1=None, mode2=None,
         npz_potential=None, txt_potential=None, peak_function='local',
         savez=False, threshold=5e-3, shift=None, interpolate=0,
         limits=[1e-2, 0.99, 5e-2, 0.95], dryrun=False, no_mayavi=False,
         interactive=False, filter='gauss'):
    """Generate greens_code potentials from *.ascii files.

        Parameters:
        -----------
            pphw: int
                points per halfwave
            N: int
                number of open modes
            L, W: float
                system length, width
            sigmax, sigmay: float
                potential extension in x- and y-direction in % of width W
            amplitude: float
                potential amplitude
            r_nx, r_ny: int
                number of gridpoints in x- and y-direction
            plot: bool
                whether to plot wavefunctions and potentials
            pic_ascii: bool
                build potential from pic.*.ascii files
            write_peaks: int (1|2)
                whether to construct a potential from mode 1 or 2
            mode1, mode2: str
                *.ascii file of mode 1 and 2
            npz_potential: str
                if supplied, use .npz file as input
            txt_potential: str
                use peaks from external text file
            peak_function: str
                determines how the potential is constructed from the
                wavefunction intensity
            savez: bool
                whether to save the output arrays in .npz format
            threshold: float
                use values < threshold*max(|psi|^2) to construct the potential
            shift: str
                use lower.dat to shift the mesh indices such that the potential
                is not distorted
            interpolate: int
                if > 0, interpolate the peaks data with n points to obtain a
                smooth potential landscape
            limits: list of floats
                determines the X- and Y-masks in percent:
                    x in [X*limits[0], X*limits[1]]
                    y in [Y*limits[2], Y*limits[4]]
            dryrun: bool
                write settings files and exit
            no_mayavi: bool
                whether to produce a 3D plot of the potential
            interactive: bool
                whether to open an interactive plot window to select indiviual
                points
            filter: str (gauss|uniform)
                chooses which filter to apply
    """
    settings = json.dumps(vars(), sort_keys=True, indent=4)
    print settings
    with open(FILE_NAME + '.json', 'w') as f:
        f.write(settings)
    convert_json_to_cfg(infile=FILE_NAME + '.json',
                        outfile=FILE_NAME + '.cfg')

    if dryrun:
        sys.exit()

    if npz_potential:
        npz_file = np.load(npz_potential)
        X, Y, Z_1, Z_2, P, x, y = [npz_file[s] for s in ('X', 'Y', 'Z_1',
                                                         'Z_2', 'P', 'x', 'y')]
    else:
        ascii_array_kwargs = {'L': L,
                              'W': W,
                              'pphw': pphw,
                              'N': N,
                              'r_nx': r_nx,
                              'r_ny': r_ny,
                              'pic_ascii': pic_ascii,
                              'return_abs': True}
        print "\nReading .ascii files..."
        try:
            pool = multiprocessing.Pool(processes=2)
            R = [pool.apply_async(read_ascii_array, args=(m,),
                                  kwds=ascii_array_kwargs) for m in (mode1,
                                                                     mode2)]
            (X, Y, Z_1), (_, _, Z_2) = [r.get() for r in R]
        except:
            X, Y, Z_1 = read_ascii_array(mode1, **ascii_array_kwargs)
            _, _, Z_2 = read_ascii_array(mode2, **ascii_array_kwargs)

    if write_peaks:
        if write_peaks == '1':
            Z = Z_1
        elif write_peaks == '2':
            Z = Z_2

        print "Building potential based on mode {}...".format(write_peaks)
        P = np.zeros_like(X)

        if len(limits) != 4:
            raise Exception("Error: len(limits) != 4.")
        # define waveguide geometry (avoid minima due to boundary conditions
        # at walls)
        X_mask = np.logical_and(limits[0]*L < X, X < limits[1]*L)
        Y_mask = np.logical_and(limits[2]*W < Y, Y < limits[3]*W)
        if pic_ascii:
            Y_mask = np.logical_and(PIC_ASCII_YMIN*W < Y, Y < PIC_ASCII_YMAX*W)
        WG_mask = np.logical_and(X_mask, Y_mask)

        if 'local' in peak_function:
            peaks = get_local_peaks(Z, peak_type='minimum')
            peaks[~WG_mask] = 0.0
        elif 'points' in peak_function:
            peaks = np.logical_and(Z < threshold*Z.max(), WG_mask)

        # get array-indices of peaks and sort coordinates
        idx = np.where(peaks)
        print "Found {} peaks...".format(len(idx[0]))
        x, y = [u[idx].flatten() for u in (X, Y)]
        x, y = [u[np.argsort(x)] for u in (x, y)]

        if txt_potential:
            print "Loading txt_potential..."
            x, y = np.loadtxt(txt_potential, unpack=True)

        if interactive:
            print "Starting interactive session..."
            from matplotlib import pyplot as plt

            fig, ax = plt.subplots()
            ax.pcolormesh(X, Y, Z, picker=PICKER_TOLERANCE)
            ax.scatter(x, y, s=5e1, c="w", edgecolors=None)
            ax.set_xlim(X.min(), X.max())
            ax.set_ylim(Y.min(), Y.max())

            fig.canvas.callbacks.connect('pick_event', on_pick)
            fig.canvas.callbacks.connect('key_press_event', on_key)

            plt.show()
            x, y = np.loadtxt(FILE_NAME + '_interactive.dat', unpack=True)

        if interpolate:
            print "Interpolating data points..."
            from scipy.interpolate import splprep, splev

            tck, _ = splprep([x, y], s=0.0, k=1)
            x, y = splev(np.linspace(0, 1, interpolate), tck)

        # reapply limits
        x_mask = np.logical_and(x > L*limits[0], x < L*limits[1])
        x, y = [u[x_mask] for u in x, y]

        # always write the potential coordinates
        print "Writing coordinates file..."
        np.savetxt(FILE_NAME + '.dat', zip(x, y))

        # write potential to grid-points
        for xi, yi in zip(x, y):
            # TODO: factor was 1.05 - introduces bugs?
            eps = W/P.shape[0]*1.10
            zi = np.where(np.logical_and(abs(X - xi) < eps,
                                         abs(Y - yi) < eps))
            P[zi] = POT_CUTOFF_VALUE

        # sigma here is in % of waveguide width W (r_ny) [caveat: P = P(y,x)]
        sigmax, sigmay = [P.shape[0]*s/100. for s in sigmax, sigmay]

        # decorate data points with filter
        if 'uniform' in filter:
            P = uniform_filter(P, (sigmay, sigmax), mode='constant')
        elif 'gauss' in filter:
            P = gaussian_filter(P, (sigmay, sigmax), mode='constant')

        # normalize potential based on most frequent value P_ij < 0.
        cutoff = stats.mode(P[P < 0.])[0][0]
        P[P < 0.99*cutoff] = POT_CUTOFF_VALUE
        P /= -P.min()

        if 'sine' in peak_function:
            print "Applying sine envelope..."
            L0 = L*(limits[1] - limits[0])/2.
            envelope = np.sin(np.pi/(2.*L0)*(X - L*limits[0]))
            P *= envelope

        if shift:
            print "Shifting indices of target array..."
            _, v = np.loadtxt(shift, unpack=True)
            for i, vi in enumerate(v):
                P[:, i] = np.roll(P[:, i], -int(vi), axis=0)

        # scale potential
        P *= amplitude

        print "Writing potential based on mode {}...".format(write_peaks)
        np.savetxt("mode_{}_peaks_potential.dat".format(write_peaks),
                   list(enumerate(P.flatten('F'))))
        if savez:
            print "Writing .npz file..."
            np.savez(FILE_NAME + '.npz',
                     X=X, Y=Y, Z_1=Z_1, Z_2=Z_2, P=P, x=x, y=y)

    if plot:
        print "Plotting wavefunctions..."
        import matplotlib
        from matplotlib import pyplot as plt
        from ep.plot import get_colors

        matplotlib.rcParams.update({'font.size': PLOT_FONTSIZE})

        f, (ax1, ax2) = plt.subplots(nrows=2, figsize=PLOT_FIGSIZE)
        get_colors()
        cmap = plt.cm.get_cmap('parula')

        # scattering wavefunction
        ax1.pcolormesh(X, Y, Z_1, cmap=cmap)
        ax2.pcolormesh(X, Y, Z_2, cmap=cmap)

        if write_peaks:
            ax1.scatter(x, y, s=1.5e4, c="w", edgecolors=None)
            ax2.scatter(x, y, s=1.5e4, c="w", edgecolors=None)

        # if npz_potential:
        #     X_nodes = npz_file['x']
        #     Y_nodes = npz_file['y']
        #     ax1.scatter(X_nodes, Y_nodes, s=1e4, c="k", edgecolors=None)
        #     ax2.scatter(X_nodes, Y_nodes, s=1e4, c="k", edgecolors=None)

        for ax in (ax1, ax2):
            ax.set_xlim(X.min(), X.max())
            ax.set_ylim(Y.min(), Y.max())

        plt.savefig(FILE_NAME + '_wavefunction.png', bbox_inches='tight')

        print "Plotting 2D potential..."
        f, ax = plt.subplots(figsize=(PLOT_FIGSIZE_SCALING*L,
                                      PLOT_FIGSIZE_SCALING*W))
        ax.set_xlim(X.min(), X.max())
        ax.set_ylim(Y.min(), Y.max())
        ax.grid(True)
        p = ax.pcolormesh(X, Y, P, cmap=cmap)
        f.colorbar(p)
        ax.set_aspect('equal', 'datalim')
        plt.savefig(FILE_NAME + '_potential_2D.png')

        if not no_mayavi:
            try:
                print "Plotting 3D potential..."
                from mayavi import mlab

                mlab.figure(size=(1024, 756))
                extent = (0, 1, 0, 5, 0, 1)
                p = mlab.surf(-P, extent=extent)
                cmap = cmap(np.arange(256))*255.
                p.module_manager.scalar_lut_manager.lut.table = cmap
                mlab.view(distance=7.5)
                mlab.savefig(FILE_NAME + '_potential_3D.png')
            except:
                print "Error: potential image not written."


if __name__ == '__main__':
    argh.dispatch_command(main)

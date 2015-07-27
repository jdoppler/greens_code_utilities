#!/usr/bin/env python2.7

import json
import numpy as np
from scipy.ndimage.filters import gaussian_filter

import argh

from ascii_to_numpy import read_ascii_array
from ep.helpers import get_local_peaks, get_local_minima
from ep.potential import gauss
from helper_functions import convert_to_complex


@argh.arg('--mode1', type=str)
@argh.arg('--mode2', type=str)
@argh.arg('--potential', type=str)
@argh.arg('--txt-potential', type=str)
@argh.arg('--write-peaks', type=str)
@argh.arg('--r-nx', type=int)
@argh.arg('--r-ny', type=int)
@argh.arg('--shift', type=str)
def main(pphw=50, N=2.5, L=100., W=1., sigmax=10., sigmay=1.,
         amplitude=1., r_nx=None, r_ny=None, plot=False,
         pic_ascii=False, write_peaks=None, mode1=None, mode2=None,
         potential=None, txt_potential=None, peak_function='local',
         savez=False, threshold=5e-3, shift=None):
    """Generate greens_code potentials from *.ascii files.

        Parameters:
        -----------
            pphw: int
            N: int
            L: float
            W: float
            sigmax: float
            sigmay: float
            amplitude: float
                potential amplitude
            r_nx: int
            r_ny: int
            plot: bool
            pic_ascii: bool
                build potential from pic.*.ascii files
            write_peaks: int (1|2)
                whether to construct a potential from mode 1 or 2
            mode1: str
                *.ascii file of mode 1
            mode2: str
                *.ascii file of mode 2
            potential: str
                if supplied, use as input
            txt_potential: str
                use peaks from external file
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
    """

    settings = json.dumps(vars(), sort_keys=True, indent=4)
    print settings
    with open("wavefunction_peaks.cfg", "w") as f:
        f.write(settings)

    print "\nReading .ascii files..."
    ascii_array_kwargs = {'L': L,
                          'W': W,
                          'pphw': pphw,
                          'N': N,
                          'r_nx': r_nx,
                          'r_ny': r_ny,
                          'pic_ascii': pic_ascii,
                          'return_abs': True}
    X, Y, Z_1 = read_ascii_array(mode1, **ascii_array_kwargs)
    _, _, Z_2 = read_ascii_array(mode2, **ascii_array_kwargs)
    print "done."

    if potential:
        P_npz = np.load(potential)
        P = P_npz['P']
        # transform maxima to minima
        P = P.max() - P

    if write_peaks:
        if write_peaks == '1':
            Z = Z_1
        elif write_peaks == '2':
            Z = Z_2

        print "Building potential based on mode {}...".format(write_peaks)
        Z_pot = np.zeros_like(X)

        X_mask = np.logical_and(0.01*L < X, X < 0.99*L)
        Y_mask = np.logical_and(0.05*W < Y, Y < 0.95*W)
        if pic_ascii:
            Y_mask = np.logical_and(0.2375*W < Y, Y < 0.75*W)
        WG_mask = np.logical_and(X_mask, Y_mask)
        sigmax, sigmay = [s/100. for s in sigmax, sigmay]  # sigma in %

        if 'local' in peak_function:
            peaks = get_local_peaks(Z, peak_type='minimum')
            # remove minma due to boundary conditions at walls
            peaks[~Y_mask] = 0.0

        elif 'points' in peak_function:
            peaks = np.logical_and(Z < threshold*Z.max(), WG_mask)
            Z_pot[np.where(peaks)] = -1.0
            # sigma here is in % of waveguide width W (r_ny)
            # caveat: Z_pot = Z_pot(y,x)
            sigmax, sigmay = [Z_pot.shape[0]*s for s in sigmax, sigmay]
            Z_pot = gaussian_filter(Z_pot, (sigmay, sigmax),
                                    mode='constant')

        # get array-indices of peaks
        idx = np.where(peaks)
        print "...found {} peaks...".format(len(idx[0]))

        if 'local' in peak_function:
            # build Gaussian potential at peaks
            x, y = [V[idx].flatten() for V in (X, Y)]
            sort = np.argsort(x)
            x, y = [V[sort] for V in (x, y)]

            if txt_potential:
                x, y = np.loadtxt(txt_potential, unpack=True)
            else:
                np.savetxt("node_positions.dat", zip(x, y))

            # scale sigma with waveguide dimensions
            sx, sy = [W*s for s in sigmax, sigmay]
            for n, (xn, yn) in enumerate(zip(x, y)):
                if n % 100 == 0:
                    print "peak number ", n
                Z_pot -= np.exp(-0.5*((X-xn)**2/sx**2+(Y-yn)**2/sy**2))

        # normalize potential
        Z_pot[Z_pot < -1.0] = -1.0
        Z_pot /= -Z_pot.min()
        print "done."

        if 'sine_truncated' in peak_function:
            Z_pot /= abs(Z_pot).max()
            Xp = 1.*X
            X0 = L/4.
            Xp[np.sin(np.pi*2.*(X-X0)/L) < 0.] = X0
            f = np.sin(np.pi*2*(Xp-X0)/L)
            Z_pot *= f/f.max()
        elif 'sine' in peak_function:
            Z_pot /= abs(Z_pot).max()
            Z_pot *= np.sin(np.pi*X/L)

        if shift:
            print "Shifting indices of target array..."
            _, v = np.loadtxt(shift, unpack=True)
            for i, vi in enumerate(v):
                Z_pot[:, i] = np.roll(Z_pot[:, i], -int(vi), axis=0)
            print "done."

        print "Writing potential based on mode {}...".format(write_peaks)
        Z_pot *= amplitude
        np.savetxt("mode_{}_peaks_potential.dat".format(write_peaks),
                   zip(range(len(Z_pot.flatten('F'))), Z_pot.flatten('F')))
        if savez:
            np.savez("mode_{}_peaks_potential.npz".format(write_peaks),
                     X=X, Y=Y, Z_1=Z_1, Z_2=Z_2, P=Z_pot,
                     X_nodes=X[idx], Y_nodes=Y[idx])
        print "done."

    if plot:
        print "Plotting wavefunctions..."
        from matplotlib import pyplot as plt
        from ep.plot import get_colors

        f, (ax1, ax2) = plt.subplots(nrows=2, figsize=(200, 100))
        get_colors()
        cmap = plt.cm.get_cmap('parula')

        # scattering wavefunction
        ax1.pcolormesh(X, Y, Z_1, cmap=cmap)
        ax2.pcolormesh(X, Y, Z_2, cmap=cmap)

        if write_peaks:
            try:
                ax1.scatter(x, y, s=1.5e4, c="w", edgecolors=None)
                ax2.scatter(x, y, s=1.5e4, c="w", edgecolors=None)
            except:
                ax1.scatter(X[idx], Y[idx], s=1.5e4, c="w", edgecolors=None)
                ax2.scatter(X[idx], Y[idx], s=1.5e4, c="w", edgecolors=None)

        if potential:
            X_nodes = P_npz['X_nodes']
            Y_nodes = P_npz['Y_nodes']
            ax1.scatter(X_nodes, Y_nodes, s=1e4, c="k", edgecolors=None)
            ax2.scatter(X_nodes, Y_nodes, s=1e4, c="k", edgecolors=None)

        for ax in (ax1, ax2):
            ax.set_xlim(X.min(), X.max())
            ax.set_ylim(Y.min(), Y.max())

        plt.savefig('wavefunction.png', bbox_inches='tight')
        if savez:
            np.savez('wavefunction.npz', X=X, Y=Y, Z_1=Z_1, Z_2=Z_2)
        print "done."

        print "Plotting potential..."
        try:
            from mayavi import mlab
            extent = (0, 1, 0, 5, 0, 1)
            p = mlab.surf(-Z_pot, extent=extent)
            p.module_manager.scalar_lut_manager.lut.table = cmap(np.arange(256))*255.
            mlab.savefig('potential.png')
        except:
            print "Error: potential.png not written."
        print "done."


if __name__ == '__main__':
    argh.dispatch_command(main)

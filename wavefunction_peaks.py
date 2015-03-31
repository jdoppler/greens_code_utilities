#!/usr/bin/env python2.7

import json
from matplotlib import pyplot as plt
import numpy as np

import argh

from ascii_to_numpy import read_ascii_array
from ep.helpers import get_local_peaks, get_local_minima
from ep.potential import gauss
from helper_functions import convert_to_complex


@argh.arg('--mode1', type=str)
@argh.arg('--mode2', type=str)
@argh.arg('--potential', type=str)
@argh.arg('--write-peaks', type=str)
@argh.arg('--r-nx', type=int)
@argh.arg('--r-ny', type=int)
def main(pphw=50, N=2.5, L=100, W=1, sigma=0.01, plot=False, r_nx=None, r_ny=None,
         pic_ascii=False, write_peaks=None, mode1=None, mode2=None,
         potential=None, peak_function='local'):

    settings = json.dumps(vars(), sort_keys=True, indent=4)
    print settings
    with open("potential.cfg", "w") as f:
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
        if peak_function == 'local':
            peaks = get_local_peaks(Z, peak_type='minimum')

            # remove minma due to boundary conditions at walls
            peaks[np.logical_or(Y > 0.95, Y < 0.05)] = 0.0

        elif peak_function == 'cut':
            Y_mask = np.logical_and(0.1 < Y, Y < 0.9)
            peaks = np.logical_and(Z < 1e4*Z.min(), Y_mask)

        # get array-indices of peaks
        idx = np.where(peaks)
        print "...found {} peaks...".format(len(idx[0]))

        # build Gaussian potential at peaks
        Z_pot = np.zeros_like(X)
        for (xn, yn) in zip(X[idx].flatten(), Y[idx].flatten()):
            Z_pot -= gauss(X, xn, sigma) * gauss(Y, yn, sigma)
        print "done."

        print "Writing potential based on mode {}...".format(write_peaks)
        np.savetxt("mode_{}_peaks_potential.dat".format(write_peaks),
                   zip(range(len(Z_pot.flatten('F'))), Z_pot.flatten('F')))
        np.savez("mode_{}_peaks_potential.npz".format(write_peaks),
                 X=X, Y=Y, Z_1=Z_1, Z_2=Z_2, P=Z_pot,
                 X_nodes=X[idx], Y_nodes=Y[idx])
        print "done."

    if plot:
        print "Plotting wavefunctions..."
        f, (ax1, ax2) = plt.subplots(nrows=2, figsize=(200, 100))
        cmap = plt.cm.jet

        # scattering wavefunction
        ax1.pcolormesh(X, Y, Z_1, cmap=cmap)
        ax2.pcolormesh(X, Y, Z_2, cmap=cmap)

        if write_peaks:
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
        np.savez('wavefunction.npz', X=X, Y=Y, Z_1=Z_1, Z_2=Z_2)
        print "done."


if __name__ == '__main__':
    argh.dispatch_command(main)

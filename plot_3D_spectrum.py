#!/usr/bin/env python2.7

import numpy as np
import matplotlib.pyplot as plt
try:
    import mayavi.mlab as mlab
except:
    print "Warning: mayavi.mlab not found!"
import sys

import argh


def unique_array(a):
    """Remove duplicate entries in an array.
    Partially taken from https://gist.github.com/jterrace/1337531
    """
    ncols = a.shape[1]
    unique_a, idx = np.unique(a.view([('', a.dtype)] * ncols), return_index=True)
    unique_a = unique_a.view(a.dtype).reshape(-1, a.shape[1])

    return unique_a, idx


def reorder_file(infile="bloch.tmp", outfile="bloch_reordered.tmp"):
    """Reorder a file containing a function on a shuffled meshgrid."""

    eps, delta, ev0r, ev0i, ev1r, ev1i = np.loadtxt(infile, unpack=True)

    ev0 = ev0r+1j*ev0i
    ev1 = ev1r+1j*ev1i

    len_eps = len(np.unique(eps))
    len_delta = len(np.unique(delta))
    print len_eps
    print len_delta

    print len(eps)
    _, idx = unique_array(np.array(zip(eps, delta)))
    eps, delta, ev0, ev1 = [ x[idx] for x in eps, delta, ev0, ev1 ]
    print len(eps)

    idx = np.lexsort((delta, eps))
    eps, delta, ev0, ev1 = [ x[idx] for x in eps, delta, ev0, ev1 ]

    v = np.array(zip(eps, delta, ev0.real, ev0.imag, ev1.real, ev1.imag))

    len_eps = len(np.unique(eps))
    len_delta = len(np.unique(delta))
    print "len(eps)", len(np.unique(eps))
    print "len(delta)", len(np.unique(delta))

    np.savetxt(outfile, v, fmt='%.18f')


@argh.arg("-p", "--png", type=str)
@argh.arg("-l", "--limits", type=float, nargs="+")
def plot_3D_spectrum(infile="bloch.tmp", outfile=False,
                     reorder=False, jump=100., mayavi=False, limits=None,
                     girtsch=False, sort=False, png=None, full=False):
    """Visualize the eigenvalue spectrum with mayavi.mlab's mesh (3D) and
    matplotlib's pcolormesh (2D).

        Parameters:
        -----------
            infile: str
                Input file.
            outfile: bool
                Whether to reordere the arrays.
            reorder: bool
                Whether to properly sort the input array.
            jump: float
                Whether to remove jump in the eigenvalue surface that exceed
                a given value.
            mayavi: bool
                Whether to produce 3D plots. If false, heatmaps are plotted.
            limits: list
                Set the x- and ylim: [xmin, xmax, ymin, ymax]
            girtsch: bool
                Whether to account for a wrong eps <-> delta labeling.
            sort: bool
                Sorts the eigenvalues such that one is larger than the other.
            png: str
                Save the heatmap plots in a .png file.
            full: bool
                Add additional heatmap plots.
    """
    if reorder:
        print "reordering..."
        reorder_file(infile, infile.replace(".dat", "_reordered.dat"))
        sys.exit()

    if girtsch:
        eps, delta, ev0, ev1 = np.loadtxt(infile, dtype=complex).T
        # wrong labeling!
        len_eps, len_delta = [ len(np.unique(x)) for x in eps, delta ]
    else:
        eps, delta, ev0r, ev0i, ev1r, ev1i = np.loadtxt(infile).T
        ev0 = ev0r + 1j*ev0i
        ev1 = ev1r + 1j*ev1i
        len_eps, len_delta = [ len(np.unique(x)) for x in eps, delta ]

    if reorder:
        ind = np.lexsort((delta, eps))
        eps, delta, ev0, ev1 = [ x[ind] for x in eps, delta, ev0, ev1 ]

    if sort:
        tmp0, tmp1 = 1.*ev0, 1.*ev1
        tmp0[ev1 > ev0] = ev1[ev1 > ev0]
        tmp1[ev1 > ev0] = ev0[ev1 > ev0]

        ev0, ev1 = 1.*tmp0, 1.*tmp1

    # get eps/delta meshgrid
    try:
        eps, delta, ev0, ev1 = [ x.reshape(len_eps, len_delta) for
                                                    x in eps, delta, ev0, ev1 ]
    except ValueError as e:
        print e
        print "shape(eps)", eps.shape
        print "shape(delta)", delta.shape

    # set x/y limits
    if limits:
        eps_min, eps_max = limits[:2]
        delta_min, delta_max = limits[2:]
        mask = ((eps > eps_min) & (eps < eps_max) &
                (delta > delta_min) & (delta < delta_max))
        for X in eps, delta, ev0, ev1:
            X[~mask] = np.nan

    # remove Nan values
    ev0 = np.ma.masked_where(np.isnan(ev0), ev0)
    ev1 = np.ma.masked_where(np.isnan(ev1), ev1)

    # print minimum of eigenvalue difference
    i, j = np.unravel_index(np.sqrt((ev0.real-ev1.real)**2 +
                                    (ev0.imag-ev1.imag)**2).argmin(), ev0.shape)
    print "Approximate EP location:"
    print "eps_EP =", eps[i,j]
    print "delta_EP =", delta[i,j]

    if mayavi:
        # real part
        for e in ev0, ev1:
            mask = np.zeros_like(eps).astype(bool)
            mask[np.abs(np.diff(e.real, axis=0)) > jump] = True
            mask[np.abs(np.diff(e.real, axis=1)) > jump] = True
            mask[np.abs(np.diff(e.imag, axis=0)) > jump] = True
            mask[np.abs(np.diff(e.imag, axis=1)) > jump] = True

            # e[mask] = np.nan
            fig = mlab.figure(0, bgcolor=(0.5,0.5,0.5))
            m = mlab.mesh(eps.real, delta.real, e.real, mask=mask)
            m.actor.actor.scale = (5,1,1)

        mlab.title("Real part", opacity=0.25)
        mlab.axes(color=(0,0,0), nb_labels=3, xlabel="epsilon", ylabel="delta",
                  zlabel="Re(K)")

        # imag part
        fig = mlab.figure(1, bgcolor=(0.5,0.5,0.5))
        for e in ev0, ev1:
            mlab.mesh(eps.real, delta.real, e.imag)
            m.actor.actor.scale = (5,1,1)
        mlab.title("Imaginary part", opacity=0.25)
        mlab.axes(color=(0,0,0), nb_labels=3, xlabel="epsilon", ylabel="delta",
                  zlabel="Im(K)")
        mlab.show()
    elif full:
        f, axes = plt.subplots(nrows=4, ncols=2, sharex=True, sharey=True)
        (ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8) = axes

        plt.xticks(rotation=70)
        plt.suptitle(infile)

        ax1.set_title(r"$\Re K_0$")
        im1 = ax1.pcolormesh(eps, delta, ev0.real, cmap=plt.get_cmap('coolwarm'))
        ax2.set_title(r"$\Im K_0$")
        im2 = ax2.pcolormesh(eps, delta, ev0.imag, cmap=plt.get_cmap('coolwarm'))
        ax3.set_title(r"$\Re K_1$")
        im3 = ax3.pcolormesh(eps, delta, ev1.real, cmap=plt.get_cmap('coolwarm'))
        ax4.set_title(r"$\Im K_1$")
        im4 = ax4.pcolormesh(eps, delta, ev1.imag, cmap=plt.get_cmap('coolwarm'))

        ax5.set_title(r"$|\Re K_0 - \Re K_1|^2$")
        Z_real = abs(ev1.real - ev0.real)
        im5 = ax5.pcolormesh(eps, delta, Z_real, cmap=plt.get_cmap('gray'), vmin=0)
        ax6.set_title(r"$|\Im K_0 - \Im K_1|^2$")
        Z_imag = abs(ev1.imag - ev0.imag)
        im6 = ax6.pcolormesh(eps, delta, Z_imag, cmap=plt.get_cmap('gray'), vmin=0)

        Z = np.sqrt(Z_imag**2 + Z_real**2)
        ax7.set_title(r"$\sqrt{(\Re K_0 - \Re K_1)^2 + (\Im K_0 - \Im K_1)^2}$")
        im7 = ax7.pcolormesh(eps, delta, Z, cmap=plt.get_cmap('gray'), vmin=0)

        Z = (Z_imag**2 + Z_real**2)**0.25
        ax8.set_title(r"$\sqrt[4]{(\Re K_0 - \Re K_1)^2 + (\Im K_0 - \Im K_1)^2}$")
        im8 = ax8.pcolormesh(eps, delta, Z, cmap=plt.get_cmap('gray'), vmin=0)

        for im, ax in zip((im1, im2, im3, im4, im5, im6, im7, im8),
                          (ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8)):
            ax.set_xlabel("epsilon")
            ax.set_ylabel("delta")
            ax.set_xlim(eps.min(), eps.max())
            ax.set_ylim(delta.min(), delta.max())
            f.colorbar(im, ax=ax)
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()
        if png:
            plt.savefig(png)
        else:
            plt.show()
    else:
        f, ax = plt.subplots(nrows=1, ncols=1, sharex=True, sharey=True)

        plt.xticks(rotation=70)
        plt.suptitle(infile)

        Z_real = abs(ev1.real - ev0.real)
        Z_imag = abs(ev1.imag - ev0.imag)
        Z = np.sqrt(Z_imag**2 + Z_real**2)

        ax.set_title(r"$\sqrt{(\Re K_0 - \Re K_1)^2 + (\Im K_0 - \Im K_1)^2}$")

        # OLD
        # im = ax.pcolormesh(eps, delta, np.log(Z), cmap=plt.get_cmap('Blues_r'))

        # add one column and row to meshgrids such that meshgrid doesn't cut 
        # away any important data
        eps_u = np.unique(eps)
        delta_u = np.unique(delta)
        eps0, delta0 = np.meshgrid(np.concatenate((eps_u, [2*eps.max()])),
                                   np.concatenate((delta_u, [2*delta.max()])))
        Z0 = np.c_[Z, Z[:,-1]]
        Z0 = np.vstack((Z0, Z0[-1]))
        im = ax.pcolormesh(eps0.T, delta0.T, np.log(Z0), cmap=plt.get_cmap('Blues_r'))
                          # vmin=0., vmax=1., shading='gouraud')

        # correct ticks
        xoffset = np.diff(eps_u).mean()/2
        yoffset = np.diff(delta_u).mean()/2
        ax.set_xticks(eps_u + xoffset)
        ax.set_yticks(delta_u + yoffset)

        # ticklabels
        ax.set_xticklabels(np.around(eps_u, decimals=4))
        ax.set_yticklabels(np.around(delta_u, decimals=4))

        # axis labels
        ax.set_xlabel("epsilon")
        ax.set_ylabel("delta")
        ax.set_xlim(eps.min(), eps.max() + 2*xoffset)
        ax.set_ylim(delta.min(), delta.max() + 2*yoffset)

        f.colorbar(im, ax=ax)

        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        plt.subplots_adjust(top=0.875)

        if png:
            plt.savefig(png)
        else:
            plt.show()


if __name__ == '__main__':
    argh.dispatch_command(plot_3D_spectrum)

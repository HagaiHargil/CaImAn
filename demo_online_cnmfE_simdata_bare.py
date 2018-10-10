"""commit 07e349cbd87a17d301b9415e37c2b1bfe8c54d1a"""
try:
    get_ipython().magic(u'load_ext autoreload')
    get_ipython().magic(u'autoreload 2')
except:
    print('NOT IPYTHON')

import caiman as cm
from caiman.source_extraction import cnmf
from caiman.base.rois import register_ROIs
from copy import deepcopy
import matplotlib.pyplot as plt
import numpy as np
from operator import itemgetter
from scipy.io import loadmat
from scipy.stats import pearsonr


small = True
save_figs = False


gSig = 3   # gaussian width of a 2D gaussian kernel, which approximates a neuron
gSiz0 = 7   # average diameter of a neuron
min_corr = .9
min_pnr = 15
s_min = -10
initbatch = 100
expected_comps = 200


fname = 'test_sim.mat'
test_sim = loadmat(fname)
(A, C, b, A_cnmfe, f, C_cnmfe, Craw_cnmfe, b0, sn, Yr, S_cnmfe,
    A_cnmfe_patch, C_cnmfe_patch, Craw_cnmfe_patch) = itemgetter(
    'A', 'C', 'b', 'A_cnmfe', 'f', 'C_cnmfe', 'Craw_cnmfe', 'b0', 'sn', 'Y', 'S_cnmfe',
    'A_cnmfe_patch', 'C_cnmfe_patch', 'Craw_cnmfe_patch')(test_sim)
dims = (253, 316)
nA = np.sqrt(np.sum(A**2, 0))
A /= nA
C *= nA[:, None]

if small:
    # A = A.reshape(dims + (-1,), order='F')[64:128, 64:160].reshape((-1, A.shape[-1]), order='F')
    A = A.reshape(dims + (-1,), order='F')[30:158, 20:148].reshape((-1, A.shape[-1]), order='F')
    keep = (A**2).sum(0) > .05
    A = A[:, keep]
    C = C[keep]
N, T = C.shape

try:
    # Yr, dims, T = cm.load_memmap('Yr_d1_64_d2_96_d3_1_order_C_frames_2000_.mmap' if small
    #                              else 'Yr_d1_253_d2_316_d3_1_order_C_frames_2000_.mmap')
    Yr, dims, T = cm.load_memmap('Yr_d1_128_d2_128_d3_1_order_C_frames_2000_.mmap' if small
                                 else 'Yr_d1_253_d2_316_d3_1_order_C_frames_2000_.mmap')
    Y = Yr.T.reshape((T,) + dims, order='F')
except IOError:
    Y = Yr.T.reshape((-1,) + dims, order='F')
    if small:
        # Y = Y[:, 64:128, 64:160]
        Y = Y[:, 30:158, 20:148]
    fname_new = cm.save_memmap([Y], base_name='Yr', order='C')
    Yr, dims, T = cm.load_memmap(fname_new)
    Y = Yr.T.reshape((T,) + dims, order='F')


#%% RUN (offline) CNMF-E algorithm on the entire batch for sake of comparison

cnm_batch = cnmf.CNMF(2, method_init='corr_pnr', k=None, gSig=(gSig, gSig), gSiz=(gSiz0, gSiz0),
                      merge_thresh=.9, p=1, tsub=1, ssub=1, only_init_patch=True, gnb=0,
                      min_corr=min_corr, min_pnr=min_pnr, s_min=s_min, normalize_init=False,
                      ring_size_factor=18. / gSiz0, center_psf=True, ssub_B=2, init_iter=1)

cnm_batch.fit(Y)

print(('Number of components:' + str(cnm_batch.estimates.A.shape[-1])))


def tight():
    plt.xlim(0, dims[1])
    plt.ylim(0, dims[0])
    plt.axis('off')
    plt.xticks([])
    plt.yticks([])


Cn, pnr = cm.summary_images.correlation_pnr(Y, gSig=gSig, center_psf=True, swap_dim=False)
plt.figure()
crd = cm.utils.visualization.plot_contours(A, Cn, thr=.8, lw=3, display_numbers=False)
crd = cm.utils.visualization.plot_contours(cnm_batch.estimates.A, Cn, thr=.8, c='r')
tight()
plt.savefig('online1p_batch.pdf', pad_inches=0, bbox_inches='tight') if save_figs else plt.show()
cm.base.rois.register_ROIs(A, cnm_batch.estimates.A, dims, align_flag=0)


#%% RUN (offline) CNMF-E algorithm on the initial batch

cnm_init = cnmf.CNMF(2, method_init='corr_pnr', k=None, gSig=(gSig, gSig), gSiz=(gSiz0, gSiz0),
                     merge_thresh=.98, p=1, tsub=1, ssub=1, only_init_patch=True, gnb=0,
                     min_corr=min_corr, min_pnr=min_pnr, s_min=s_min, normalize_init=False,
                     ring_size_factor=18. / gSiz0, center_psf=True, ssub_B=2, init_iter=1,
                     minibatch_shape=100, minibatch_suff_stat=5, update_num_comps=True,
                     rval_thr=.9, thresh_fitness_delta=-30, thresh_fitness_raw=-50,
                     batch_update_suff_stat=True)

cnm_init.fit(Y[:initbatch])

print(('Number of components:' + str(cnm_init.estimates.A.shape[-1])))

Cn_init, pnr_init = cm.summary_images.correlation_pnr(
    Y[:initbatch], gSig=gSig, center_psf=True, swap_dim=False)
plt.figure()
crd = cm.utils.visualization.plot_contours(A, Cn_init, thr=.8, lw=3, display_numbers=False)
crd = cm.utils.visualization.plot_contours(cnm_init.estimates.A, Cn_init, thr=.8, c='r')
tight()
plt.savefig('online1p_init.pdf', pad_inches=0, bbox_inches='tight') if save_figs else plt.show()
cm.base.rois.register_ROIs(A, cnm_init.estimates.A, dims, align_flag=0)


#%% run (online) CNMF-E algorithm

gSiz = 13
estim = deepcopy(cnm_init.estimates)
estim.A = estim.A[:, :1]
estim.YrA = estim.YrA[:1]
estim.C = estim.C[:1]
cnm = cnmf.online_cnmf.OnACID(cnm_init.params, estim)
cnm.params.set('data', {'dims': dims})
cnm._prepare_object(np.asarray(Yr[:, :initbatch]), T)
cnm.params.set('init', {'gSiz' : (gSiz, gSiz), 'ring_size_factor' : 18. / gSiz})
cnm.params.set('online', {'min_num_trial': 1, 'max_num_added': 1, 'thresh_CNN_noisy' : None}) 
t = initbatch
# cnm.params.online['rval_thr'] = .9995
# cnm.params.online['thresh_fitness_raw'] = -40
for frame in Y[initbatch:]:
    cnm.fit_next(t, frame.copy().reshape(-1, order='F'))
    t += 1


print(('Number of components:' + str(cnm.estimates.Ab.shape[-1])))

plt.figure()
crd = cm.utils.visualization.plot_contours(A, Cn, thr=.8, lw=3, display_numbers=False)
crd = cm.utils.visualization.plot_contours(cnm.estimates.Ab, Cn, thr=.8, c='r')
tight()
plt.savefig('online1p_online.pdf', pad_inches=0, bbox_inches='tight') if save_figs else plt.show()
cm.base.rois.register_ROIs(A, cnm.estimates.Ab, dims, align_flag=0)


#%% second run

cnm2 = deepcopy(cnm)
cnm2.C_on = np.zeros((cnm.C_on.shape[0], 2 * T), dtype=np.float32)
cnm2.noisyC = np.zeros((cnm.noisyC.shape[0], 2 * T), dtype=np.float32)
cnm2.C_on[:, :T] = cnm.C_on
cnm2.noisyC[:, :T] = cnm.noisyC
# cnm2.rval_thr = .9
# cnm.thresh_fitness_raw = -70
t = T
for frame in Y:
    cnm2.fit_next(t, frame.copy().reshape(-1, order='F'))
    t += 1

cnm2.C_on = cnm2.C_on[:, T:]
cnm2.noisyC = cnm2.noisyC[:, T:]


#%% third run

cnm3 = deepcopy(cnm2)
cnm3.C_on = np.zeros((cnm2.C_on.shape[0], 2 * T), dtype=np.float32)
cnm3.noisyC = np.zeros((cnm2.noisyC.shape[0], 2 * T), dtype=np.float32)
cnm3.C_on[:, :T] = cnm2.C_on
cnm3.noisyC[:, :T] = cnm2.noisyC
cnm3.update_num_comps = False
t = T
for frame in Y:
    cnm3.fit_next(t, frame.copy().reshape(-1, order='F'))
    t += 1

cnm3.C_on = cnm3.C_on[:, T:]
cnm3.noisyC = cnm3.noisyC[:, T:]


#%% compare online to batch

print('RSS of W:  online vs init:' +
      '{0:.3f}'.format((cnm.W - cnm_init.W).power(2).sum()).rjust(10))
print('            batch vs init:' +
      '{0:.3f}'.format((cnm_batch.W - cnm_init.W).power(2).sum()).rjust(10))
print('          online vs batch:' +
      '{0:.3f}'.format((cnm.W - cnm_batch.W).power(2).sum()).rjust(10))
print('         online2 vs batch:' +
      '{0:.3f}'.format((cnm2.W - cnm_batch.W).power(2).sum()).rjust(10))
print('         online3 vs batch:' +
      '{0:.3f}'.format((cnm3.W - cnm_batch.W).power(2).sum()).rjust(10))

#%% compare to ground truth 

matched_ROIs1b, matched_ROIs2b, non_matched1b, non_matched2b, performanceb, A2b = register_ROIs(
    A, cnm_batch.A, dims, align_flag=False)
matched_ROIs1, matched_ROIs2, non_matched1, non_matched2, performance, A2 = register_ROIs(
    A, cnm.Ab, dims, align_flag=False)
matched_ROIs1i, matched_ROIs2i, non_matched1i, non_matched2i, performancei, A2i = register_ROIs(
    A, cnm_init.A, dims, align_flag=False)
matched_ROIs1s, matched_ROIs2s, non_matched1s, non_matched2s, performances, A2s = register_ROIs(
    A, cnm2.Ab, dims, align_flag=False)

# traces
cor_batch = [pearsonr(c1, c2)[0] for (c1, c2) in
             np.transpose([C[matched_ROIs1b], cnm_batch.C[matched_ROIs2b]], (1, 0, 2))]
cor = [pearsonr(c1, c2)[0] for (c1, c2) in
       np.transpose([C[matched_ROIs1], cnm.C_on[matched_ROIs2]], (1, 0, 2))]
cor2 = [pearsonr(c1, c2)[0] for (c1, c2) in
        np.transpose([C[matched_ROIs1s], cnm2.C_on[matched_ROIs2s]], (1, 0, 2))]
cor3 = [pearsonr(c1, c2)[0] for (c1, c2) in
        np.transpose([C[matched_ROIs1s], cnm3.C_on[matched_ROIs2s]], (1, 0, 2))]

print('Correlation  mean +- std    median')
for l, c in (('  batch', cor_batch), (' online', cor), ('online2', cor2), ('online3', cor3)):
    print('  ' + l + ':  {0:.4f}+-{1:.4f}  {2:.4f}'.format(np.mean(c), np.std(c), np.median(c)))


plt.figure(figsize=(20, N))
for i in range(N):
    plt.subplot(N, 1, 1 + i)
    plt.plot(C[i], c='k', lw=4, label='truth')
    try:
        plt.plot(cnm_batch.C[matched_ROIs2b[list(matched_ROIs1b).index(i)]],
                 c='r', lw=3, label='batch')
    except ValueError:
        pass
    try:
        plt.plot(cnm.C_on[matched_ROIs2[list(matched_ROIs1).index(i)]],
                 c='y', lw=2, label='online')
    except ValueError:
        pass
    try:
        plt.plot(cnm2.C_on[matched_ROIs2s[list(matched_ROIs1s).index(i)]],
                 c='b', lw=1, label='online 2nd pass')
    except ValueError:
        pass
    if i == 0:
        plt.legend(ncol=3)
plt.tight_layout()
plt.savefig('online1p_traces.pdf') if save_figs else plt.show()

# shapes
over_batch = [c1.dot(c2) / np.sqrt(c1.dot(c1) * c2.dot(c2)) for (c1, c2) in
              np.transpose([A.T[matched_ROIs1b],
                            cnm_batch.A.toarray().T[matched_ROIs2b]], (1, 0, 2))]
over = [c1.dot(c2) / np.sqrt(c1.dot(c1) * c2.dot(c2)) for (c1, c2) in
        np.transpose([A.T[matched_ROIs1], cnm.Ab.toarray().T[matched_ROIs2]], (1, 0, 2))]
over2 = [c1.dot(c2) / np.sqrt(c1.dot(c1) * c2.dot(c2)) for (c1, c2) in
         np.transpose([A.T[matched_ROIs1s], cnm2.Ab.toarray().T[matched_ROIs2s]], (1, 0, 2))]
over3 = [c1.dot(c2) / np.sqrt(c1.dot(c1) * c2.dot(c2)) for (c1, c2) in
         np.transpose([A.T[matched_ROIs1s], cnm3.Ab.toarray().T[matched_ROIs2s]], (1, 0, 2))]
over_init = [c1.dot(c2) / np.sqrt(c1.dot(c1) * c2.dot(c2)) for (c1, c2) in
             np.transpose([A.T[matched_ROIs1i], cnm_init.A.toarray().T[matched_ROIs2i]], (1, 0, 2))]

print('Overlap    mean +- std    median')
for l, c in (('  batch', over_batch), ('   init', over_init), (' online', over),
             ('online2', over2), ('online3', over3)):
    print(l + ':  {0:.4f}+-{1:.4f}  {2:.4f}'.format(np.mean(c), np.std(c), np.median(c)))

#%% sorted ring weights

d1, d2 = (np.array(dims) + 1) // 2
ringidx = cnm._ringidx
circ = len(ringidx[0])


def get_angle(x, y):
    x = float(x)
    y = float(y)
    if x == 0:
        return np.pi / 2 if y > 0 else np.pi / 2 * 3
    else:
        if x < 0:
            return np.arctan(y / x) + np.pi
        else:
            if y >= 0:
                return np.arctan(y / x)
            else:
                return np.arctan(y / x) + 2 * np.pi


sort_by_angle = np.argsort([get_angle(ringidx[0][i], ringidx[1][i])
                            for i in range(circ)])


def sort_W(W):
    Q = np.zeros((d1 * d2, circ)) * np.nan
    for i in range(d1 * d2):
        pixel = np.unravel_index(i, (d1, d2), order='F')
        x = pixel[0] + ringidx[0]
        y = pixel[1] + ringidx[1]
        inside = (x >= 0) * (x < d1) * (y >= 0) * (y < d2)
        Q[i, inside] = W.data[W.indptr[i]:W.indptr[i + 1]]
    Q = Q[:, sort_by_angle]
    return Q


Q_batch = sort_W(cnm_batch.W)
Q_init = sort_W(cnm_init.W)
Q = sort_W(cnm.W)
Q2 = sort_W(cnm2.W)

plt.figure()
plt.plot(np.nanmean(Q_init, 0), label='init')
plt.plot(np.nanmean(Q_batch, 0), label='batch')
plt.plot(np.nanmean(Q, 0), label='online')
plt.plot(np.nanmean(Q2, 0), label='online 2nd pass')
plt.legend()
plt.xlabel('Pixel on ring')
plt.ylabel('Average ring weight')
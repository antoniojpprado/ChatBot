import numpy as np
import matplotlib
import matplotlib.pyplot as plt


fig = plt.figure()
Z = np.arange(10000).reshape((100, 100))
Z[:, 50:] = 1

im1 = fig.figimage(Z, xo=50, yo=0, origin='lower')
im2 = fig.figimage(Z, xo=100, yo=100, alpha=.8, origin='lower')

plt.savefig('logo_equiplex.png', bbox_inches='tight', format='png')
plt.show()

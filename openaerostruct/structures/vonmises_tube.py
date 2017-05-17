from __future__ import print_function, division
import numpy as np

from openmdao.api import ExplicitComponent

from openaerostruct.structures.utils import norm, unit

try:
    import OAS_API
    fortran_flag = True
    data_type = float
except:
    fortran_flag = False
    data_type = complex

class VonMisesTube(ExplicitComponent):
    """ Compute the von Mises stress in each element.

    inputeters
    ----------
    nodes[ny, 3] : numpy array
        Flattened array with coordinates for each FEM node.
    radius[ny-1] : numpy array
        Radii for each FEM element.
    disp[ny, 6] : numpy array
        Displacements of each FEM node.

    Returns
    -------
    vonmises[ny-1, 2] : numpy array
        von Mises stress magnitudes for each FEM element.

    """

    def initialize(self):
        self.metadata.declare('surface', type_=dict)

    def initialize_variables(self):
        self.surface = surface = self.metadata['surface']

        self.ny = surface['num_y']

        self.add_input('nodes', val=np.zeros((self.ny, 3),
                       dtype=data_type))
        self.add_input('radius', val=np.zeros((self.ny - 1),
                       dtype=data_type))
        self.add_input('disp', val=np.zeros((self.ny, 6),
                       dtype=data_type))

        self.add_output('vonmises', val=np.zeros((self.ny-1, 2),
                        dtype=data_type))

        self.E = surface['E']
        self.G = surface['G']

        self.T = np.zeros((3, 3), dtype=data_type)
        self.x_gl = np.array([1, 0, 0], dtype=data_type)

    def initialize_partials(self):
        if not fortran_flag:
            self.approx_partials('*', '*')

    def compute(self, inputs, outputs):
        radius = inputs['radius']
        disp = inputs['disp']
        nodes = inputs['nodes']
        vonmises = outputs['vonmises']
        T = self.T
        E = self.E
        G = self.G
        x_gl = self.x_gl

        if fortran_flag:
            vm = OAS_API.oas_api.calc_vonmises(nodes, radius, disp, E, G, x_gl)
            outputs['vonmises'] = vm

        else:

            num_elems = self.ny - 1
            for ielem in range(self.ny-1):

                P0 = nodes[ielem, :]
                P1 = nodes[ielem+1, :]
                L = norm(P1 - P0)

                x_loc = unit(P1 - P0)
                y_loc = unit(np.cross(x_loc, x_gl))
                z_loc = unit(np.cross(x_loc, y_loc))

                T[0, :] = x_loc
                T[1, :] = y_loc
                T[2, :] = z_loc

                u0x, u0y, u0z = T.dot(disp[ielem, :3])
                r0x, r0y, r0z = T.dot(disp[ielem, 3:])
                u1x, u1y, u1z = T.dot(disp[ielem+1, :3])
                r1x, r1y, r1z = T.dot(disp[ielem+1, 3:])

                tmp = np.sqrt((r1y - r0y)**2 + (r1z - r0z)**2)
                sxx0 = E * (u1x - u0x) / L + E * radius[ielem] / L * tmp
                sxx1 = E * (u0x - u1x) / L + E * radius[ielem] / L * tmp
                sxt = G * radius[ielem] * (r1x - r0x) / L

                vonmises[ielem, 0] = np.sqrt(sxx0**2 + sxt**2)
                vonmises[ielem, 1] = np.sqrt(sxx1**2 + sxt**2)

    def compute_jacvec_product(
            self, inputs, outputs, d_inputs, d_outputs, mode):

        radius = inputs['radius'].real
        disp = inputs['disp'].real
        nodes = inputs['nodes'].real
        vonmises = outputs['vonmises'].real
        E = self.E
        G = self.G
        x_gl = self.x_gl

        if mode == 'fwd':
            _, vonmisesd = OAS_API.oas_api.calc_vonmises_d(nodes, d_inputs['nodes'], radius, d_inputs['radius'], disp, d_inputs['disp'], E, G, x_gl)
            d_outputs['vonmises'] += vonmisesd

        if mode == 'rev':
            nodesb, radiusb, dispb = OAS_API.oas_api.calc_vonmises_b(nodes, radius, disp, E, G, x_gl, vonmises, d_outputs['vonmises'])
            d_inputs['nodes'] += nodesb
            d_inputs['radius'] += radiusb
            d_inputs['disp'] += dispb
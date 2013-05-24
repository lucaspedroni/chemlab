"""Pick objects on screen
"""
import numpy as np
from .transformations import unit_vector, angle_between_vectors, rotation_matrix
import time

class SpherePicker(object):
    
    def __init__(self, widget, positions, radii):
        
        self.positions = positions
        self.radii = np.array(radii)
        self.widget = widget
        
    def pick(self, x, y):
        # X and Y are normalized coordinates
        
        # Origin of the ray, object space
        origin = self.widget.camera.unproject(x, y)
        
        # Another point to get the direction
        dest = self.widget.camera.unproject(x, y, 0.0) 
        
        # direction of the ray
        direction = unit_vector(dest - origin)
        
        #intersections = []
        #distances = []
        # Quadratic equation for the intersection
        # for i, r in enumerate(self.positions):
        #     a = 1.0 # d . d
        #     b = 2*np.dot((origin - r), direction)
        #     c = np.dot((origin - r), (origin - r)) - self.radii[i]**2
            
        #     det =  b*b - 4*a*c
            
        #     if det >= 0.0:
        #         intersections.append(i)
        #         t = (b + np.sqrt(det))/(2*a)
        #         distances.append(t)
        
        # print time.time() - t

        # Vectorized intersections. This is just a numpy-vectorize
        # version of the above algorithm
        
        b_v = 2.0 * ((origin - self.positions) * direction).sum(axis=1)
        c_v = ((origin - self.positions)**2).sum(axis=1) - self.radii ** 2
        det_v = b_v * b_v - 4.0 * c_v
        
        inters_mask = det_v >= 0
        intersections = (inters_mask).nonzero()[0]
        distances = (b_v[inters_mask] + np.sqrt(det_v[inters_mask])) / 2.0
        
        # We need only the thing in front of us, that corresponts to
        # negative distances. Probably we simply have the wrong
        # direction intersection.
        
        dist_mask = distances < 0.0
        distances = distances[dist_mask]
        intersections = intersections[dist_mask].tolist()
        
        if intersections:
            distances, intersections = zip(*sorted(zip(distances, intersections)))
            return list(reversed(intersections))
        else:
            return intersections
            
class CylinderPicker(object):

    def __init__(self, widget, bounds, radii):
        self.widget = widget
        self.bounds = bounds
        self.radii = radii
        self.directions = bounds[:, 1, :] - bounds[:, 0, :]
        self.origins = bounds[:, 0, :]
        # The center of the bounding sphere
        centers = 0.5 * (bounds[:, 1, :] + bounds[:, 0, :])
        # The radii of the bounding spheres
        radii = 0.5 * np.sqrt((self.directions**2).sum(axis=1))
        self._bounding_sphere = SpherePicker(widget, centers, radii)

    def _origin_ray(self, x, y):
        # X and Y are normalized coordinates
        # Origin of the ray, object space
        origin = self.widget.camera.unproject(x, y)
        
        # Another point to get the direction
        dest = self.widget.camera.unproject(x, y, 0.0) 
        
        # direction of the ray
        direction = unit_vector(dest - origin)
        
        return origin, direction

    def pick(self, x, y):
        origin, direction = self._origin_ray(x, y)

        # First, take only the things intersection with the bounding spheres
        sph_intersections = self._bounding_sphere.pick(x, y)
        #print('Sph intersections', sph_intersections)
        
        # Now, do the proper intersection with the cylinders
        z_axis = np.array([0.0, 0.0, 1.0])

        intersections = []
        for i in sph_intersections:
            # 1) Change frame of reference of the origin and direction
            # Rotation matrix
            M = rotation_matrix(
                angle_between_vectors(self.directions[i], z_axis),
                np.cross(self.directions[i], z_axis))[:3, :3]
            
            cyl_origin = self.origins[i]
            origin_p = M.dot(origin - cyl_origin)
            direction_p = M.dot(direction)
            
            origin_p[-1] = 0.0
            direction_p[-1] = 0.0
            # 2) Intersection between ray and z-aligned cylinder
            cyl_radius = self.radii[i]
            
            a = direction_p.dot(direction_p)
            b = 2.0 * origin_p.dot(direction_p)
            c = origin_p.dot(origin_p) - cyl_radius*cyl_radius
            det = b**2 - 4*a*c

            if det >= 0.0:
                # Hit
                print 'Hit!', i
                t = -b + np.sqrt(det)/(2.0*a)
                intersections.append((i, t))
                
        return intersections
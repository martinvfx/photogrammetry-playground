import cv2
import numpy as np
import scipy

from TargetDetectorBase import TargetDetectorBase
from Target import Square
from Target import Ellipse as _Ellipse
import Target

class DefaultDetector(TargetDetectorBase):

    '''
    Finds targets by calculating an adaptive thresholded image, on which it
    finds squares and ellipses from the contours on the thresholded image. From
    these lists it looks for targets that follow the Photomodeler encoding
    system and marks them as RAD targets and it looks for the smaller unencoded
    targets.

    returns nothing.

    self.radtargets contain the ellipses of the RAD targets
    self.smalltargets contains the ellipses of the unencoded targets

    # TODO fix this output to be consistent
    '''

    def __init__(self, image=None):
        super(DefaultDetector, self).__init__(image)
        self.detector_name = 'DefaultDetector'
        self.threshold = self.get_threshold()
        self.contours_hierarchy = self.get_contours()
        self.square_contours = self.find_square_contours()

    def _find_ellipses(self):
        ''' finds all the ellipses in the image
        '''
        ellipses = []
        hulls = []
        # for each contour, fit an ellipse
        for i, ch in enumerate(self.contours_hierarchy):
            cnt = ch[0]
            # get convex hull of contour
            hull = cv2.convexHull(cnt, returnPoints=True)
            # defects = cv2.convexityDefects(cnt, hull)

            if len(hull) > 5:
                # (x,y), (Ma, ma), angle = cv2.fitEllipse(hull)
                ellipse = cv2.fitEllipse(np.array(hull))
                ellipses.append(ellipse)
                hulls.append(hulls)

        return ellipses, hulls

    def find_targets(self):
        ''' Finds all the targets on itself
        '''
        # Find all the ellipses in the image. We are looking for the biggest
        # ellipse that fits inside on of the squares.

        ellipses, hulls = self._find_ellipses()
        self.ellipses = ellipses

        radtargets = []
        for ell in self.ellipses:
            (x, y), (Ma, ma), angle = ell
            outer_enc, inner_enc = self.find_rad_encoding(self.threshold, ell)
            if (outer_enc == "011111111111"):
                if (inner_enc.startswith('1')) and (inner_enc != '1'*12):
                    target = Target.Target(x, y, 'RAD', inner_enc)
                    target.ellipse = ell
                    radtargets.append(target)

        self.radtargets = radtargets

        smalltargets = []
        for sq in self.square_contours:
            for ell in self.ellipses:
                (x, y), (Ma, ma), angle = ell
                Ma = max(Ma, ma)
                if sq.containsPoint((x, y)) > 0:
                    if 0.5*sq.longside > Ma/2.0:
                        if Ma/2.0 > 0.15*sq.longside:
                            target = Target.Target(x, y, 'circle', 'none')
                            target.ellipse = ell
                            smalltargets.append(target)
        small_target_kdtree = self._create_ellipse_kdtree(smalltargets)
        # now go through the rad targets and remove the smalltargets inside
        _to_remove = []
        for rad in self.radtargets:
            (x, y), (Ma, ma), angle = rad.ellipse
            # find the small targets within one major axis from rad center
            nearest = small_target_kdtree.query_ball_point((x,y), Ma/2.)
            for n in nearest:
                _to_remove.append(smalltargets[n])

        for rem in _to_remove:
            try:
                smalltargets.remove(rem)
            except:
                pass

        self.smalltargets = smalltargets

    def find_rad_encoding(self, img, radtarget, plot=False):
        ''' given an image and a rad target ellipse pair, find the encoding used

        return as a string containing 1 and 0 i.e. encoding='101010101010'

        '''
        (x, y), (Ma, ma), angle = radtarget
        outer = _Ellipse(x, y, 0.85*Ma, 0.85*ma, angle)
        inner = _Ellipse(x, y, 0.6*Ma, 0.6*ma, angle)

        pouter, theta_outer, imval_outer =\
            self.find_imval_at_ellipse_coordinates(img, outer, n=200)
        pinner, theta_inner, imval_inner =\
            self.find_imval_at_ellipse_coordinates(img, inner, n=200)

        try:
            # get the angles where the image value along the ellipse is zero
            theta_min = np.min(theta_outer[imval_outer == 0]*180/np.pi)
            # find the index of the smallest angle where this is true
            start = np.where(theta_outer*180/np.pi == theta_min)[0][0]
            # now roll the array so that it start at that index
            imval_outer = np.roll(imval_outer, -start)
            imval_outer_split = np.array_split(imval_outer, 12)
            imval_inner = np.roll(imval_inner, -start)
            imval_inner_split = np.array_split(imval_inner, 12)
            # now split that array into 12 nearly equally sized pieces
            # the median value should be either 255 or 0, calculate the encoding
            for i, segment in enumerate(imval_outer_split):
                if np.median(segment) == 255:
                    imval_outer_split[i] = '1'
                else:
                    imval_outer_split[i] = '0'
            outer_enc = ''.join(imval_outer_split)
            # same for inner
            for i, segment in enumerate(imval_inner_split):
                if np.median(segment) == 255:
                    imval_inner_split[i] = '1'
                else:
                    imval_inner_split[i] = '0'
            inner_enc = ''.join(imval_inner_split)

        except ValueError as ve:
            #print ve
            outer_enc, inner_enc = '999999999999', '999999999999'

        # some bug fixing plots
        if plot:
            fig = plt.figure(figsize=(12, 12))
            ax1 = fig.add_subplot(111, aspect='equal')
            intMa = int(Ma)
            plt.imshow(img, cmap=matplotlib.cm.gray, interpolation='nearest')
            ell1 = radtarget
            e1 = matplotlib.patches.Ellipse((x, y), Ma, ma, angle,
                         facecolor='none', edgecolor='r')
#           # make ellipse for the inner encoding ring
#           e3 = Ellipse((ell2.x, ell2.y), ell2.Ma*(0.5), ell2.ma*(0.5),
#                        ell2.angle+90, facecolor='none', edgecolor='b')
#           # make ellipse for the outer encoding ring
#           e4 = Ellipse((ell2.x, ell2.y), ell2.Ma*(0.9), ell2.ma*(0.9),
#                        ell2.angle+90, facecolor='none', edgecolor='b')
            ax1.add_artist(e1)
#           ax1.add_artist(e2)
#           ax1.add_artist(e3)
#           ax1.add_artist(e4)
            plt.xlim(x-intMa, x+intMa)
            plt.ylim(y-intMa, y+intMa)
            plt.title(encoding)

            # TODO Roll the array so that the minimum of the outer ring is
            # at the start of the array, then calculate the values in the 12 bits

            plt.show()

        return outer_enc, inner_enc

    def _create_ellipse_kdtree(self, targets):
        ''' Given list of ellipses as return from _find_ellipses
            return the kd-tree made from their coordinates
        '''

        data = np.zeros((len(targets), 2), dtype='float')

        for i, target in enumerate(targets):
            (x, y), (Ma, ma), angle = target.ellipse
            data[i, 0] = x
            data[i, 1] = y

        kdtree = scipy.spatial.KDTree(data)

        return kdtree

    def find_imval_at_ellipse_coordinates(self, img, ellipse, n=100):
        ''' Given rotated ellipse, return n coordinates along its perimeter '''
        # x=acos(theta) y=bsin(theta)
        theta = (ellipse.angle + 90)*np.pi/180.
        angles = np.linspace(0, 2*np.pi, n)
        # center of ellipse
        x0, y0 = ellipse.x, ellipse.y

        x = ellipse.Ma/2.0*np.cos(angles)
        y = ellipse.ma/2.0*np.sin(angles)

        xy = np.array([(x[i], y[i]) for i, xx in enumerate(x)]).T
        # rotation matrix
        rotMat = np.array([[np.sin(theta), -1.0*np.cos(theta)],
                           [np.cos(theta), np.sin(theta)]])

        rotatedXY = np.dot(rotMat, xy).T

        rotatedXY[:, 0] += y0
        rotatedXY[:, 1] += x0
        # round to ints
        rotatedXY = np.around(rotatedXY, 0)

        # find image values
        imval = []
        for row in rotatedXY:
            x, y = row[0], row[1]
            try:
                imval.append(img[x, y])
            except IndexError:
                imval.append(0)

        imval = np.array(imval)
        # regions are either high or low. make high regions = 255 and low
        # regions == 1.0
        imval_max = imval.max()

        imval[imval > 0.25*imval_max] = 255
        imval[imval <= 0.25*imval_max] = 0
        return rotatedXY, angles, np.array(imval)

    def find_square_contours(self, epsilon=0.1, min_area=200, max_area=4000):
        ''' Find the ones that is approximately square
        '''

        squares = []
        for ch in self.contours_hierarchy:
            cnt = ch[0]
            area = abs(cv2.contourArea(cnt))
            err = epsilon*cv2.arcLength(cnt, True)
            hull = cv2.convexHull(cnt)
            approx = cv2.approxPolyDP(hull, err, True)
            if len(approx) != 4:
                continue
            if area < min_area:
                continue
            if area > max_area:
                continue
            square = Square(approx)
            squares.append(square)

        return squares

import os
import struct
import json
import random
from argparse import ArgumentParser
from logging import getLogger
import numpy as np
from PIL import Image
from skimage.transform import resize
from skimage.morphology import dilation, disk, skeletonize, erosion, closing
import fire


np.random.seed(123)  # TODO
logger = getLogger()
__all__ = ["MNISTthin"]
AVAILABLE_ATTR = ["R", "G", "B"]


class MNISTthin:
    def __init__(
        self,
        which_set,
        path,
        background="blue-red",
        shade=True,
        label_type="even-odd",
        clr_ratio=[0.5, 0.5],
        green_yellow=True,
        egr=0.5,
        ogr=0.5,
        sensitiveattr="bck",
        transform_list=[],
        out_channels=3,
    ):

        # downloads data if not present
        # download_data(path)

        if which_set in ["train", "val"]:
            self.images = np.load(os.path.join(path, "train-images.npy"))
            self.labels = np.load(os.path.join(path, "train-labels.npy"))
        else:
            self.images = np.load(os.path.join(path, "test-images.npy"))
            self.labels = np.load(os.path.join(path, "test-labels.npy"))

        # split
        ntotal = self.images.shape[0]
        ntrain = 50000
        if which_set == "train":
            self.images = self.images[:ntrain]
            self.labels = self.labels[:ntrain]
        elif which_set == "val":
            self.images = self.images[ntrain:]
            self.labels = self.labels[ntrain:]
        pad_images = np.zeros(
            (self.images.shape[0], self.images.shape[1] +
             4, self.images.shape[2] + 4),
            dtype=self.images.dtype,
        )
        pad_images[
            :, 4: 4 + self.images.shape[1], 4: 4 + self.images.shape[1]
        ] = self.images
        # pad_images[:, 2: 2 + self.images.shape[1],
        #            2: 2 + self.images.shape[1]] = self.images
        self.images = pad_images
        print("Number of images: ", len(self.images), which_set)
        print("Number of labels: ", len(self.labels), which_set)

        # class attributes
        self.transform = None
        self.n_classes = 2
        self.out_channels = out_channels
        assert sensitiveattr in ["bck", "color_gy"]
        self.sensitiveattr = sensitiveattr

        # adding channels
        if out_channels > 1:
            self.images = np.tile(
                self.images[:, :, :, np.newaxis], out_channels)
        # self.img, self.att, lbl = self.load_colored_mnist(bck=background, label=label_type, clr_ratio=clr_ratio)
        self.img, self.att, lbl = self.load_multivariable_mnist(
            bck=background,
            shade=shade,
            label=label_type,
            clr_ratio=clr_ratio,
            green_yellow=green_yellow,
            egr=egr,
            ogr=ogr,
        )
        self.att = self.att[self.sensitiveattr]
        self.eo_lbl = (lbl % 2 == 0).astype(np.uint8)
        self.lbl = lbl

    def __len__(self):
        return len(self.images)

    def load_multivariable_mnist(
        self,
        bck="blue-red",
        shade=True,
        label="cat-digits",
        clr_ratio=[],
        green_yellow=True,
        egr=0.5,
        ogr=0.5
    ):
        """This module returns
        MNIST digits with
        bck=blue-red ::: blue or red background with a ratio of clr_ratio
        bck=black    ::: original MNIST
        labels:
        even-odd   :::  1=even or 0=odd.
        cat-digits ::: categorical labels
        clr_ratio[0] (clr_ratio[1]) refers to the ratio of blue in even (odd) digits
        """
        assert bck in ["blue-red", "black"]

        shffl_1st = np.arange(self.images.shape[0])
        np.random.shuffle(shffl_1st)
        assert self.images.shape[-1] == 3
        if shade:
            dtype = np.float32
            c = 1.0
        else:
            c = 255.0
            dtype = np.float32
        image = (self.images * c).astype(dtype)

        mask = self.images[:, :, :, :].copy()
        mask = (mask > 0.5).astype(np.uint8)
        label = self.labels
        all_att = {}
        if bck == "blue-red":
            even_odd_label = (label % 2 == 0).astype(np.uint8)
            num_imgs_o = mask[even_odd_label == 0].shape[0]
            num_imgs_e = mask[even_odd_label == 1].shape[0]
            be_ratio = int(clr_ratio[0] * even_odd_label.sum())
            bo_ratio = int(
                clr_ratio[1] * (mask.shape[0] - even_odd_label.sum()))

            if shade:
                be = np.zeros((be_ratio, 32, 32, 3), dtype=dtype)
                re = np.zeros((num_imgs_e - be_ratio, 32, 32, 3), dtype=dtype)
                be[:, :, :, 2:3] = (
                    255
                    * np.ones((be_ratio, 32, 32, 1), dtype=dtype)
                    * np.random.uniform(0.90, 1.0, size=(be_ratio, 32, 32, 1))
                )
                be[:, :, :, 0:2] = (
                    255
                    * np.random.uniform(0.0, 0.10, size=(be_ratio, 32, 32, 2))
                    * np.ones((be_ratio, 32, 32, 2), dtype=dtype)
                )

                re[:, :, :, 1:3] = (
                    255
                    * np.random.uniform(
                        0.0, 0.10, size=(num_imgs_e - be_ratio, 32, 32, 2)
                    )
                    * np.ones((num_imgs_e - be_ratio, 32, 32, 2), dtype=dtype)
                )
                re[:, :, :, 0:1] = (
                    255
                    * np.ones((num_imgs_e - be_ratio, 32, 32, 1), dtype=dtype)
                    * np.random.uniform(
                        0.90, 1.0, size=(num_imgs_e - be_ratio, 32, 32, 1)
                    )
                )
            else:
                be = np.zeros((be_ratio, 32, 32, 3), dtype=dtype)
                re = np.zeros((num_imgs_e - be_ratio, 32, 32, 3), dtype=dtype)
                be[:, :, :, 2:3] = 255 * \
                    np.ones((be_ratio, 32, 32, 1), dtype=dtype)
                re[:, :, :, 0:1] = 255 * np.ones(
                    (num_imgs_e - be_ratio, 32, 32, 1), dtype=dtype
                )

            be = c * (be * (1 - (self.images[even_odd_label == 1]
                                 > 0.5).astype(dtype)[:be_ratio]))

            x = 1 - (self.images[even_odd_label == 1]
                     <= 0.5).astype(dtype)[:be_ratio]
            if shade:
                y = np.random.uniform(
                    0.90, 1.0, size=x.shape) * np.ones(x.shape)
            else:
                y = 1.0
            be = be + (255.0 * x * y)

            assert be.shape == (be_ratio, *image.shape[1:])
            re = c * (re* (1- (self.images[even_odd_label == 1]
                       > 0.5).astype(dtype)[be_ratio:]))
            x = 1 - (self.images[even_odd_label == 1]
                     <= 0.5).astype(dtype)[be_ratio:]
            if shade:
                y = np.random.uniform(
                    0.90, 1.0, size=x.shape) * np.ones(x.shape)
            else:
                y = 1.0
            re = re + (255.0 * x * y)

            if shade:
                bo = np.zeros((bo_ratio, 32, 32, 3), dtype=dtype)
                ro = np.zeros((num_imgs_o - bo_ratio, 32, 32, 3), dtype=dtype)
                bo[:, :, :, 2:3] = (
                    255
                    * np.ones((bo_ratio, 32, 32, 1), dtype=dtype)
                    * np.random.uniform(0.90, 1.0, size=(bo_ratio, 32, 32, 1))
                )
                bo[:, :, :, 0:2] = (
                    255
                    * np.random.uniform(0.0, 0.10, size=(bo_ratio, 32, 32, 2))
                    * np.ones((bo_ratio, 32, 32, 2), dtype=dtype)
                )

                ro[:, :, :, 0:1] = (
                    255
                    * np.ones((num_imgs_o - bo_ratio, 32, 32, 1), dtype=dtype)
                    * np.random.uniform(
                        0.90, 1.0, size=(num_imgs_o - bo_ratio, 32, 32, 1)
                    )
                )
                ro[:, :, :, 1:3] = (
                    255
                    * np.random.uniform(
                        0.0, 0.10, size=(num_imgs_o - bo_ratio, 32, 32, 2)
                    )
                    * np.ones((num_imgs_o - bo_ratio, 32, 32, 2), dtype=dtype)
                )
            else:
                bo = np.zeros((bo_ratio, 32, 32, 3), dtype=dtype)
                ro = np.zeros((num_imgs_o - bo_ratio, 32, 32, 3), dtype=dtype)
                bo[:, :, :, 2:3] = 255 * \
                    np.ones((bo_ratio, 32, 32, 1), dtype=dtype)
                ro[:, :, :, 0:1] = 255 * np.ones(
                    (num_imgs_o - bo_ratio, 32, 32, 1), dtype=dtype
                )
            bo = c * (bo * (1 - (self.images[even_odd_label == 0]
                       > 0.5).astype(dtype)[:bo_ratio]))
            x = 1 - (self.images[even_odd_label == 0]
                     <= 0.5).astype(dtype)[:bo_ratio]
            if shade:
                y = np.random.uniform(
                    0.90, 1.0, size=x.shape) * np.ones(x.shape)
            else:
                y = 1.0

            bo = bo + (255.0 * x * y)
            assert bo.shape == (bo_ratio, *image.shape[1:])
            ro = c * (ro * (1 - (self.images[even_odd_label == 0]
                       > 0.5).astype(dtype)[bo_ratio:]))
            x = 1 - (self.images[even_odd_label == 0]
                     <= 0.5).astype(dtype)[bo_ratio:]
            if shade:
                y = np.random.uniform(
                    0.90, 1.0, size=x.shape) * np.ones(x.shape)
            else:
                y = 1.0

            ro = ro + (255.0 * x * y)
            image[even_odd_label == 1] += np.concatenate([be, re], axis=0)
            image[even_odd_label == 0] += np.concatenate([bo, ro], axis=0)

            image = image[shffl_1st]
            mask = mask[shffl_1st]
            label = label[shffl_1st]
            even_odd_label = (label % 2 == 0).astype(np.uint8)
            np.random.shuffle(shffl_1st)

            if green_yellow:
                num_o_gt = int(num_imgs_o * ogr)
                num_e_gt = int(num_imgs_e * egr)
                num_e_yt = num_imgs_e - num_e_gt
                num_o_yt = num_imgs_o - num_o_gt
                color_gy = np.ones((image.shape[0])).astype("uint8")

                count_e, count_o = 0, 0
                for i in range(image.shape[0]):
                    if even_odd_label[i] == 1:
                        if count_e < num_e_gt:
                            color_gy[i] = 0
                            count_e += 1
                    elif even_odd_label[i] == 0:
                        if count_o < num_o_gt:
                            color_gy[i] = 0
                            count_o += 1

                for i in range(image.shape[0]):

                    if color_gy[i] == 0:
                        p = 6
                        for k in range(4):
                            for m in range(4):
                                (
                                    image[i][k, p + m, 0],
                                    image[i][k, p + m, 1],
                                    image[i][k, p + m, 2],
                                ) = (255.0 / 2, 255.0 / 2, 255.0 / 2)
                    elif color_gy[i] == 1:
                        p = 22
                        for k in range(4):
                            for m in range(4):
                                (
                                    image[i][k, p + m, 0],
                                    image[i][k, p + m, 1],
                                    image[i][k, p + m, 2],
                                ) = (255.0 / 2, 255.0 / 2, 255.0 / 2)

            image = image[shffl_1st]
            mask = mask[shffl_1st]
            label = label[shffl_1st]
            even_odd_label = (label % 2 == 0).astype(np.uint8)
            if green_yellow:
                color_gy = color_gy[shffl_1st].astype(np.uint8)
                all_att["color_gy"] = color_gy
            np.random.shuffle(shffl_1st)

        attribute = image[:, 3, 0, :].copy().argmax(axis=1)
        attribute[attribute == 2] = 1
        all_att["bck"] = attribute

        image_transformed = image.transpose(0, 3, 1, 2).astype("float32")
        print(np.amax(image_transformed), np.amin(image_transformed))
        return self.normalize(image_transformed), all_att, label

    def normalize(self, img):
        return (img / 255.0) * 2.0 - 1.0  # [-1, +1]
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Trains, evaluates and saves the model network using a queue."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import numpy as np
import scipy as scp
import random

import tensorflow as tf
import time

from PIL import Image, ImageDraw, ImageFont


def road_draw(image, highway):
    im = Image.fromarray(image.astype('uint8'))
    draw = ImageDraw.Draw(im)

    fnt = ImageFont.truetype('FreeMono/FreeMonoBold.ttf', 40)

    shape = image.shape

    if highway:
        draw.text((65, 10), "Highway",
                  font=fnt, fill=(255, 255, 0, 255))

        draw.ellipse([10, 10, 55, 55], fill=(255, 255, 0, 255),
                     outline=(255, 255, 0, 255))
    else:
        draw.text((65, 10), "small road",
                  font=fnt, fill=(255, 0, 0, 255))

        draw.ellipse([10, 10, 55, 55], fill=(255, 0, 0, 255),
                     outline=(255, 0, 0, 255))

    return np.array(im).astype('float32')


def eval_res(hypes, labels, output, loss):
    index = {'road': 0, 'cross': 1}[loss]
    pos_num = 0
    neg_num = 0
    fn = 0
    fp = 0
    if(labels[index] == '0'):
        neg_num = 1
        if(np.argmax(output[index]) == 1):
            fp = 1
    else:
        pos_num = 1
        if(np.argmax(output[index]) == 0):
            fn = 1

    return fn, fp, pos_num, neg_num


def evaluate(hypes, sess, image_pl, inf_out):
    if hypes["only_road"]:
        model_list = ['road']
    else:
        model_list = ['road', 'cross']

    val = evaluate_data(hypes, sess, image_pl, inf_out, validation=True)
    train = evaluate_data(hypes, sess, image_pl, inf_out, validation=False)

    eval_list = []

    for loss in model_list:
        eval_list.append(('%s  val Accuricy' % loss,
                          100*val['accuricy'][loss]))
        eval_list.append(('%s  val Precision' % loss,
                          100*val['precision'][loss]))
        eval_list.append(('%s  val Recall' % loss,
                          100*val['recall'][loss]))
        eval_list.append(('%s  train Accuricy' % loss,
                          100*train['accuricy'][loss]))
        eval_list.append(('%s  train Precision' % loss,
                          100*train['precision'][loss]))
        eval_list.append(('%s  train Recall' % loss,
                          100*train['recall'][loss]))
    eval_list.append(('Speed (msec)', 1000*val['dt']))
    eval_list.append(('Speed (fps)', 1/val['dt']))

    return eval_list, val['image_list']


def evaluate_data(hypes, sess, image_pl, inf_out, validation=True):

    softmax_road, softmax_cross = inf_out['softmax']
    data_dir = hypes['dirs']['data_dir']
    image_list = []
    if validation is True:
        data_file = hypes['data']['val_file']
    else:
        data_file = hypes['data']['train_file']
    data_file = os.path.join(data_dir, data_file)
    image_dir = os.path.dirname(data_file)

    if hypes["only_road"]:
        model_list = ['road']
    else:
        model_list = ['road', 'cross']

    total_fp = {}
    total_fn = {}
    total_posnum = {}
    total_negnum = {}
    for loss in model_list:
        total_fp[loss] = 0
        total_fn[loss] = 0
        total_posnum[loss] = 0
        total_negnum[loss] = 0

    with open(data_file) as file:
        for i, datum in enumerate(file):
            datum = datum.rstrip()
            image_file, road_type, crossing = datum.split(" ")
            labels = (road_type, crossing)
            image_file = os.path.join(image_dir, image_file)

            if random.random() > 0.3:
                continue

            image = scp.misc.imread(image_file)

            if hypes['jitter']['fix_shape']:
                shape = image.shape
                image_height = hypes['jitter']['image_height']
                image_width = hypes['jitter']['image_width']
                assert(image_height >= shape[0])
                assert(image_width >= shape[1])

                offset_x = (image_height - shape[0])//2
                offset_y = (image_width - shape[1])//2
                new_image = np.zeros([image_height, image_width, 3])
                new_image[offset_x:offset_x+shape[0],
                          offset_y:offset_y+shape[1]] = image
                input_image = new_image
            else:
                input_image = image

            shape = input_image.shape

            feed_dict = {image_pl: input_image}

            output = sess.run([softmax_road, softmax_cross],
                              feed_dict=feed_dict)

            if validation:
                highway = (np.argmax(output[0][0]) == 0)
                new_img = road_draw(input_image, highway)
                image_name = os.path.basename(image_file)
                image_list.append((image_name, new_img))

            for loss in model_list:

                FN, FP, posNum, negNum = eval_res(hypes, labels, output,
                                                  loss)

                total_fp[loss] += FP
                total_fn[loss] += FN
                total_posnum[loss] += posNum
                total_negnum[loss] += negNum

    if validation:
        start_time = time.time()
        for i in xrange(10):
            sess.run([softmax_road, softmax_cross], feed_dict=feed_dict)
        dt = (time.time() - start_time)/10
    else:
        dt = None

    accuricy = {}
    precision = {}
    recall = {}

    for loss in model_list:
        tp = total_posnum[loss] - total_fn[loss]
        tn = total_negnum[loss] - total_fp[loss]
        accuricy[loss] = (tp + tn) / (total_posnum[loss] + total_negnum[loss])
        precision[loss] = tp / (tp + total_fp[loss] + 0.000001)
        recall[loss] = tp / (total_posnum[loss] + 0.000001)

    return {'accuricy': accuricy, 'precision': precision,
            'recall': recall, 'dt': dt, 'image_list': image_list}

import tensorflow as tf
import os
import numpy as np
import datetime
import display
from matplotlib import pyplot as plt
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
from tensorflow.keras.layers import Conv2D, BatchNormalization, Activation, Dropout,  Dense, Concatenate, MaxPool2D, \
    GlobalAveragePooling2D, GlobalAveragePooling3D, Dense, add, Input, Conv3D, concatenate, multiply, DepthwiseConv2D, MaxPooling3D

init_lr = 0.001
kernel_number = 16


os.environ["CUDA_VISIBLE_DEVICES"] = "0"
gpus = tf.config.experimental.list_physical_devices(device_type='GPU')
tf.config.experimental.set_memory_growth(device=gpus[0], enable=True)
'''bn_axis = 4 if tf.keras.backend.image_data_format() == 'channels_last' else 1'''

"Multiscale share Inception Block"
def SpaE(X):
    Conv1 = Conv2D(filters=kernel_number, kernel_size=(3, 3), strides=1, padding='same')(X)
    BN1 = BatchNormalization()(Conv1)
    Relu1 = Activation('relu')(BN1)
    Conv2 = Conv2D(filters=kernel_number, kernel_size=(5, 5), strides=1, padding='same')(X)
    BN2 = BatchNormalization()(Conv2)
    Relu2 = Activation('relu')(BN2)
    Conv3 = Conv2D(filters=kernel_number, kernel_size=(7, 7), strides=1, padding='same')(X)
    BN3 = BatchNormalization()(Conv3)
    Relu3 = Activation('relu')(BN3)
    Cat1 = concatenate([Relu1, Relu2, Relu3])

    Conv4 = DepthwiseConv2D(kernel_size=(3, 3), strides=1, depth_multiplier=1, padding='same')(Cat1)
    BN4 = BatchNormalization()(Conv4)
    Relu4 = Activation('relu')(BN4)
    Conv5 = Conv2D(filters=1, kernel_size=(1, 1), strides=1, padding='same')(Cat1)
    BN5 = BatchNormalization()(Conv5)
    Relu5 = Activation('relu')(BN5)
    Cat2 = add([Relu4, Relu5])

    Conv6 = Conv2D(filters=kernel_number, kernel_size=(1, 1), strides=1, padding='same')(Cat2)
    BN6 = BatchNormalization()(Conv6)
    Relu6 = Activation('relu')(BN6)

    return Relu6


"Spatial Feature Extraction Sub-network"

def SpaM(X):
    Conv1 = Conv2D(filters=kernel_number, kernel_size=(1, 1), strides=1, padding='same')(X)
    BN1 = BatchNormalization()(Conv1)
    Relu1 = Activation('relu')(BN1)
    Block1 = SpaE(Relu1)
    Add1 = add([Relu1, Block1])
    Block2 = SpaE(Add1)
    Add2 = add([Add1, Block2])
    Block3 = SpaE(Add2)
    Add3 = add([Add2, Block3])
    GAP = GlobalAveragePooling2D()(Add3)
    return GAP

'''Spectral feature extraction'''
def SpeE(X):
    Conv1 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 7), strides=(1, 1, 2), padding='valid')(X)
    BN1 = BatchNormalization()(Conv1)
    Relu1 = Activation('relu')(BN1)
    Conv2 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 7), strides=(1, 1, 2), padding='valid')(Relu1)
    BN2 = BatchNormalization()(Conv2)
    Relu2 = Activation('relu')(BN2)

    Conv3 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 5), strides=(1, 1, 1), padding='same')(Relu2)
    BN3 = BatchNormalization()(Conv3)
    Relu3 = Activation('relu')(BN3)
    Conv4 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 5), strides=(1, 1, 1), padding='same')(Relu3)
    BN4 = BatchNormalization()(Conv4)
    Relu4 = Activation('relu')(BN4)
    Add1 = add([Relu2, Relu4])
    MaxPool1 = MaxPooling3D(pool_size=(1, 1, 5), strides=(1, 1, 1), padding='valid')(Add1)

    Conv5 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 5), strides=(1, 1, 1), padding='same')(MaxPool1)
    BN5 = BatchNormalization()(Conv5)
    Relu5 = Activation('relu')(BN5)
    Conv6 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 5), strides=(1, 1, 1), padding='same')(Relu5)
    BN6 = BatchNormalization()(Conv6)
    Relu6 = Activation('relu')(BN6)
    Add2 = add([MaxPool1, Relu6])
    MaxPool2 = MaxPooling3D(pool_size=(1, 1, 5), strides=(1, 1, 1), padding='valid')(Add2)

    return MaxPool2

def Local_speE(X):
    Local = SpeE(X)
    return Local


def NonLocal_SpeE(X):
    T = tf.split(X, num_or_size_splits=144, axis=3)
    for i in range(72):
        if i == 0:
            Concat1 = tf.concat([T[i], T[143 - i]], axis=3)
        else:
            Concat = tf.concat([T[i], T[143 - i]], axis=3)
            Concat1 = tf.concat([Concat1, Concat], axis=3)
    NonLocal = SpeE(Concat1)
    return NonLocal


'''Spectral feature extraction sub-network'''
def SpeM(X):
    Block1 = Local_speE(X)
    Block2 = NonLocal_SpeE(X)
    Output = concatenate([Block1, Block2])
    Conv1 = Conv3D(filters=kernel_number, kernel_size=(1, 1, 7), strides=1, padding='valid')(Output)
    BN1 = BatchNormalization()(Conv1)
    Relu1 = Activation('relu')(BN1)
    MaxPool1 = MaxPooling3D(pool_size=(1, 1, 5), strides=(1, 1, 1), padding='valid')(Relu1)
    GAP = GlobalAveragePooling3D()(MaxPool1)

    return GAP

"AFF modual"
def FF(X1, X2):
    Cat1 = concatenate([X1, X2], axis=1)
    FC1 = Dense(units=kernel_number*2, activation='sigmoid')(Cat1)
    Mul = multiply([FC1, Cat1])
    Add = add([Mul, Cat1])
    FC2 = Dense(units=kernel_number*2, activation='relu')(Add)

    return FC2

def AS2F2N(X1, X2):
    Path1 = SpaM(X1)
    Path2 = SpeM(X2)
    Feature_F = FF(Path1, Path2)
    return Feature_F


def M(input_shape1=(15, 15, 10), input_shape2=(3, 3, 144, 1), classes=16):
    inputs1 = Input(shape=input_shape1)
    inputs2 = Input(shape=input_shape2)
    P1 = AS2F2N(inputs1, inputs2)
    outputs = Dense(units=15, activation='softmax')(P1)
    model = tf.keras.Model(inputs=[inputs1, inputs2], outputs=outputs, name='IN_model')
    return model

model = M(input_shape1=(15, 15, 5), input_shape2=(3, 3, 144, 1), classes=16)





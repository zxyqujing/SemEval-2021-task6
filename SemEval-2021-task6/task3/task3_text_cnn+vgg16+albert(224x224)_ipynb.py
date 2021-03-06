# -*- coding: utf-8 -*-
"""task3_text_cnn+vgg16+albert(224x224).ipynb（交叉熵）

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Rd1epsNEYZqgcf2IjHBb7F4PbXG_601L
"""

# 1-24 start test
# 2-18 ALBERT+Text CNN+VGG16
# 挂载谷歌网盘
# from google.colab import drive
# drive.mount('/content/drive', force_remount=True)

# Commented out IPython magic to ensure Python compatibility.
# %cd "/content/drive/My Drive/SemEval-2021-task6(1-23)/task3"
# %ls

# !pip install transformers
# !pip install sentencepiece
#
# !nvidia-smi

import numpy as np
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer  # 多标签编码
from sklearn.model_selection import train_test_split
from load_data_task3 import load_train_data, load_dev_data, load_test_data  # 前面写的导入数据函数

from transformers import AlbertTokenizer, TFBertMainLayer, AlbertConfig, TFAlbertModel
import tensorflow as tf
from tensorflow.keras.layers import Activation
import os
from load_image import load_image
from vgg16 import VGG16
from Resnet import ResNet18
from metric import f1, Metrics

class text_cnn(tf.keras.Model):
    def __init__(self):
        super(text_cnn, self).__init__()
        self.c1 = tf.keras.layers.Conv1D(filters=64, kernel_size=(3), padding='VALID')  # 卷积层1
        self.b1 = tf.keras.layers.BatchNormalization()  # BN层1
        self.a1 = tf.keras.layers.Activation('relu')  # 激活层1
        self.p1 = tf.keras.layers.MaxPool1D(pool_size=(3), strides=2, padding='VALID')
        self.d1 = tf.keras.layers.Dropout(0.3)  # dropout层

        self.c2 = tf.keras.layers.Conv1D(filters=64, kernel_size=(4), padding='VALID')
        self.b2 = tf.keras.layers.BatchNormalization()  # BN层1
        self.a2 = tf.keras.layers.Activation('relu')  # 激活层1
        self.p2 = tf.keras.layers.MaxPool1D(pool_size=(4), strides=2, padding='VALID')
        self.d2 = tf.keras.layers.Dropout(0.3)  # dropout层

        self.c3 = tf.keras.layers.Conv1D(filters=64, kernel_size=(5), padding='VALID' )
        self.b3 = tf.keras.layers.BatchNormalization()  # BN层1
        self.a3 = tf.keras.layers.Activation('relu')  # 激活层1
        self.p3 = tf.keras.layers.MaxPool1D(pool_size=(5), strides=2, padding='VALID')
        self.d3 = tf.keras.layers.Dropout(0.3)  # dropout层

        self.flatten = tf.keras.layers.Flatten()

    def call(self, x):
        x1 = self.c1(x)
        x1 = self.b1(x1)
        x1 = self.a1(x1)
        x1 = self.p1(x1)
        x1 = self.d1(x1)
        x1 = self.flatten(x1)

        x2 = self.c2(x)
        x2 = self.b2(x2)
        x2 = self.a2(x2)
        x2 = self.p2(x2)
        x2 = self.d2(x2)
        x2 = self.flatten(x2)

        x3 = self.c3(x)
        x3 = self.b3(x3)
        x3 = self.a3(x3)
        x3 = self.p3(x3)
        x3 = self.d3(x3)
        x3 = self.flatten(x3)

        y = tf.concat([x1,x2,x3],1)
        return y

def save_result(dev_labels,dev_file,task_output_file):
    # 保存预测结果为txt文件形式
    import sys
    import json

    try:
        with open(dev_file, "r", encoding="utf8") as f:
            jsonobj = json.load(f)
    except:
        sys.exit("ERROR: cannot load json file")

    for i, example in enumerate(jsonobj):
        techniques_list = list(dev_labels[i])
        example['labels'] = techniques_list
        print("example %s: added %d labels" % (example['id'], len(techniques_list)))

    with open(task_output_file, "w") as fout:
        json.dump(jsonobj, fout, indent=4)
    print("Predictions written to file " + task_output_file)

def create_model():
    # bert层
    config = AlbertConfig.from_pretrained('albert-base-v2')
    print(config)
    bert_layer = TFAlbertModel.from_pretrained('albert-base-v2')
    initializer = tf.keras.initializers.TruncatedNormal(config.initializer_range)

    # 构建bert输入
    input_ids = tf.keras.Input(shape=(config.max_position_embeddings,), dtype='int32')
    token_type_ids = tf.keras.Input(shape=(config.max_position_embeddings,), dtype='int32')
    attention_mask = tf.keras.Input(shape=(config.max_position_embeddings,), dtype='int32')

    # 模型输入
    text_inputs = {'input_ids': input_ids, 'token_type_ids': token_type_ids, 'attention_mask': attention_mask}
    image_inputs = tf.keras.Input(shape=(224, 224, 3), dtype='float')

    # ResNet18
    resnet = ResNet18([2,2,2,2])
    image_output = resnet(image_inputs) # image output
    # vgg16 = VGG16()
    # image_output = vgg16(image_inputs)

    # bert的输出
    bert_output = bert_layer(text_inputs)
    print(bert_output)
    hidden_states = bert_output[0] # 取(seq_length,embedding_size)矩阵
    print(hidden_states)

    dropout_hidden = tf.keras.layers.Dropout(0.3)(hidden_states)
    text_cnn_layer = text_cnn()
    text_cnn_output = text_cnn_layer(dropout_hidden)
    dropout_output = tf.keras.layers.Dropout(0.3)(text_cnn_output)

    dense = tf.keras.layers.Dense(768, activation='relu')(dropout_output)
    text_output = tf.keras.layers.Dropout(0.3)(dense)

    # text和image拼接
    text_image_cocat = tf.concat([text_output, image_output], 1)
    #dense1 = tf.keras.layers.Dense(768, kernel_initializer=initializer, activation='relu')(text_image_cocat)
    #drop = tf.keras.layers.Dropout(0.2)(dense1)

    # 全连接分类
    output = tf.keras.layers.Dense(22, kernel_initializer=initializer, activation='sigmoid')(text_image_cocat)
 
    model = tf.keras.Model(inputs=[input_ids,token_type_ids,attention_mask,image_inputs], outputs=output)

    model.summary()
    return model

# 读取techiques列表
techiques_list_filename = '../techniques_list_task3.txt'
with open(techiques_list_filename, "r",encoding='utf8') as f:
    techiques_list = [line.rstrip() for line in f.readlines() if len(line) > 2]
print(len(techiques_list))

# 读取训练、验证、测试数据
train_id, train_texts, train_techiques, train_image_path = load_train_data()
train_images = np.asarray(load_image(train_image_path))

print("train data size:", len(train_texts))
print("train_image size:",len(train_images),train_images.shape)

dev_id, dev_texts, dev_techiques, dev_image_path = load_dev_data()
dev_images = np.asarray(load_image(dev_image_path))

test_id, test_texts, test_image_path = load_test_data()
test_images = np.asarray(load_image(test_image_path))

# 对标签进行编码
mlb = MultiLabelBinarizer(classes=techiques_list)
train_labels = mlb.fit_transform(train_techiques)
dev_labels = mlb.fit_transform(dev_techiques)


print("\nval data size:",len(dev_texts),len(dev_labels))
print("val_image size",len(dev_images),dev_images.shape)

print("\ntest data size:",len(test_texts),len(test_id))
print("test_image size",len(test_images),test_images.shape)


# 对文本数据编码
tokenizer = AlbertTokenizer.from_pretrained('albert-base-v2')
train_encodings = tokenizer(train_texts, truncation=True, padding='max_length')
dev_encodings = tokenizer(dev_texts, truncation=True, padding="max_length")
test_encodings = tokenizer(test_texts, truncation=True, padding="max_length")

# 将bert的三个输入转为tensor
input_ids = tf.convert_to_tensor(train_encodings['input_ids'])
token_type_ids = tf.convert_to_tensor(train_encodings['token_type_ids'])
attention_mask = tf.convert_to_tensor(train_encodings['attention_mask'])

dev_input_ids = tf.convert_to_tensor(dev_encodings['input_ids'])
dev_token_type_ids = tf.convert_to_tensor(dev_encodings['token_type_ids'])
dev_attention_mask = tf.convert_to_tensor(dev_encodings['attention_mask'])

# 模型输入为[input_ids,token_type_ids,attention_mask,images]

model = create_model()

# 断点续训
checkpoint_save_path = "./checkpoint/Albertt+Text_CNN+ResNet(2-18-sec)/muti_labels.ckpt"
if os.path.exists(checkpoint_save_path + '.index'):
    model.load_weights(checkpoint_save_path)
    print('===============Load Model=================')

cp_callback = tf.keras.callbacks.ModelCheckpoint(filepath=checkpoint_save_path,
                                                  monitor='val_f1',
                                                  verbose=1,
                                                  save_weights_only=True,
                                                  save_best_only=True,
                                                  mode='max', )

tb_callback = tf.keras.callbacks.TensorBoard(log_dir='./log/Albertt+Text_CNN+VGG16/logs', profile_batch=0)

# 训练模型
print("===============Start training=================")
optimizer = tf.keras.optimizers.Adam(lr=5e-6, epsilon=1e-8)
loss = tf.keras.losses.BinaryCrossentropy()  # 二进制交叉熵
model.compile(optimizer=optimizer, loss=loss, metrics=[f1])
history = model.fit([input_ids,token_type_ids,attention_mask,train_images],train_labels, 
                    epochs=100,
                    batch_size=8,
                    validation_data=([dev_input_ids,dev_token_type_ids,dev_attention_mask,dev_images],dev_labels), 
                    validation_freq=1,
                    callbacks=[Metrics(valid_data=([dev_input_ids,dev_token_type_ids,dev_attention_mask,dev_images],dev_labels)),
                                   cp_callback,
                                   tb_callback])

# 预测结果
from sklearn.metrics import f1_score
model.load_weights(checkpoint_save_path) # 取val最优模型
print("load_model")
y_pred = model.predict([dev_input_ids,dev_token_type_ids,dev_attention_mask,dev_images])
y_true = dev_labels

print(len(y_pred),len(y_true))
# 将结果转为0，1形式
threshold, upper, lower = 0.5, 1, 0
y_pred[y_pred > threshold] = upper
y_pred[y_pred <= threshold] = lower

print("F1 Macro:",f1_score(y_true, y_pred, average='macro',zero_division=1))  
print("F1 MICRO:",f1_score(y_true, y_pred, average='micro',zero_division=1))

# 在无标签development上预测
# 读取test数据
def load_un_dev_data(un_dev_file):
  import sys
  import json
  try:
      with open(un_dev_file, "r", encoding="utf8") as f:
          jsonobj = json.load(f)
  except:
      sys.exit("ERROR: cannot load json file")

  id, text, image = [], [], []
  for example in jsonobj:
      id.append(example['id'])
      text.append(example['text'])
      image.append('../development/dev_set_task3/' + example['image'])

  return id, text, image

unlabeled_dev_file = "../development/dev_set_task3/dev_set_task3.txt"
un_dev_id, un_dev_texts, un_dev_image_path = load_un_dev_data(unlabeled_dev_file)
un_dev_images = np.asarray(load_image(un_dev_image_path))

print(un_dev_image_path)
print("un_dev data size:", len(un_dev_texts))
print("un_dev_image size:",len(un_dev_images),un_dev_images.shape)


# 对文本数据编码
un_dev_encodings = tokenizer(dev_texts, truncation=True, padding='max_length')

# 将bert的三个输入转为tensor
un_dev_input_ids = tf.convert_to_tensor(un_dev_encodings['input_ids'])
un_dev_token_type_ids = tf.convert_to_tensor(un_dev_encodings['token_type_ids'])
un_dev_attention_mask = tf.convert_to_tensor(un_dev_encodings['attention_mask'])

y_pred = model.predict([un_dev_input_ids,un_dev_token_type_ids,un_dev_attention_mask,un_dev_images])
threshold, upper, lower = 0.5, 1, 0
y_pred[y_pred > threshold] = upper
y_pred[y_pred <= threshold] = lower

# 将结果转为labels list形式
un_dev_labels = mlb.inverse_transform(y_pred)

# 保存预测结果
un_dev_file = "../development/dev_set_task3/dev_set_task3.txt"
task_output_file = "../development/result/output-task3-Albert-Text_Cnn-ResNet.txt"
save_result(un_dev_labels,un_dev_file,task_output_file)

print(len(test_encodings['input_ids']))
# 在test上预测
test_input_ids = tf.convert_to_tensor(test_encodings['input_ids'])
test_token_type_ids = tf.convert_to_tensor(test_encodings['token_type_ids'])
test_attention_mask = tf.convert_to_tensor(test_encodings['attention_mask'])


y_pred = model.predict([test_input_ids,test_token_type_ids,test_attention_mask,test_images])
threshold, upper, lower = 0.5, 1, 0
y_pred[y_pred > threshold] = upper
y_pred[y_pred <= threshold] = lower

# 将结果转为labels list形式
test_labels = mlb.inverse_transform(y_pred)

# 保存预测结果
test_file = "../data/test_set_task3/test_set_task3.txt"
task_output_file = "./result/test-task3-Albert+TextCnn+ResNet(0.635).txt"
save_result(test_labels,test_file,task_output_file)

# !ls
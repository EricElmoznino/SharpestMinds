from __future__ import print_function
import tensorflow as tf
import Helpers as hp
import MidiManipulator as mm
from RNN_DBN import RNN_DBN
import shutil
import os
import time
from random import shuffle


class MusicGenerator:

    def __init__(self, configuration):
        self.conf = configuration
        self.manipulator = mm.MidiManipulator(self.conf.num_timesteps)

        self.rnn_rbm = RNN_DBN(self.manipulator.input_length, [100], 100)

        with tf.variable_scope('inputs'):
            self.x = tf.placeholder(tf.float32, shape=[None, self.manipulator.input_length])

        self.saver = None

    def generate(self, length, primer_song, generation_path, name, primer_length=100):
        primer_song = self.manipulator.get_song(primer_song)[0:primer_length, :]
        model = self.rnn_rbm.generation_model(self.x, length)
        with tf.Session() as sess:
            self.saver.restore(sess, os.path.join(self.conf.train_log_path, 'model.ckpt'))
            music = sess.run(model, feed_dict={self.x: primer_song})
        self.manipulator.write_song(os.path.join(generation_path, name+'.mid'), music)
        return music

    def train(self, train_path):
        if os.path.exists(self.conf.train_log_path):
            shutil.rmtree(self.conf.train_log_path)
        os.mkdir(self.conf.train_log_path)

        self.__pre_train(train_path)

        costs, optimizers, loglikelihoods, summaries = self.rnn_rbm.train_model(self.x)

        songs = self.manipulator.get_songs(hp.files_at_path(train_path), self.conf.batch_size)
        n_batches = len(songs)
        n_steps = n_batches * self.conf.epochs * len(costs)

        print('Starting training\n')
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            self.saver.restore(sess, os.path.join(self.conf.train_log_path, 'pre-train.ckpt'))
            self.saver = tf.train.Saver()

            train_writer = tf.summary.FileWriter(self.conf.train_log_path, sess.graph)

            start_time = time.time()
            step = 0
            dbn_layer = 1
            # Greedily train each layer in the dbn
            for cost, optimizer, loglikelihood, summary in zip(costs, optimizers, loglikelihoods, summaries):
                summary = tf.summary.merge(summary)
                for epoch in range(1, self.conf.epochs + 1):
                    epoch_ll = 0
                    shuffle(songs)
                    for batch in range(n_batches):
                        song_batch = songs[batch]
                        if step % max(int(n_steps / 1000), 1) == 0:
                            _, ll, s = sess.run([optimizer, loglikelihood, summary],
                                               feed_dict={self.x: song_batch})
                            train_writer.add_summary(s, step)
                        else:
                            _, ll = sess.run([optimizer, loglikelihood],
                                            feed_dict={self.x: song_batch})
                        epoch_ll += ll
                        step += 1

                    hp.log_epoch(step, n_steps, epoch, self.conf.epochs,
                                 dbn_layer, start_time, epoch_ll / n_batches)
                print('\n', 'Finished training dbn layer', dbn_layer, '\n')
                dbn_layer += 1

            self.saver.save(sess, os.path.join(self.conf.train_log_path, 'model.ckpt'))

    def __pre_train(self, train_path):
        _, optimizers = self.rnn_rbm.pretrain_model(self.x)
        self.saver = tf.train.Saver()

        songs = self.manipulator.get_songs(hp.files_at_path(train_path), self.conf.pretrain_batch_size)
        n_batches = len(songs)

        print('Starting pre-training\n')
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            # Greedily train each layer in the dbn
            for optimizer in optimizers:
                for epoch in range(self.conf.pretrain_epochs):
                    shuffle(songs)
                    for batch in range(n_batches):
                        song_batch = songs[batch]
                        sess.run(optimizer, feed_dict={self.x: song_batch})

            self.saver.save(sess, os.path.join(self.conf.train_log_path, 'pre-train.ckpt'))

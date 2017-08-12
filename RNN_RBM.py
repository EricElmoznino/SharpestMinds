import tensorflow as tf
from RBM import RBM
import Helpers as hp

class RNN_RBM:

    def __init__(self, visible_size, hidden_size, state_size, num_rnn_cells=1):
        self.v_size = visible_size
        self.h_size = hidden_size
        self.s_size = state_size
        self.num_rnn_cells = num_rnn_cells

        with tf.variable_scope('rbm'):
            self.W = hp.weight_variables([self.v_size, self.h_size], stddev=0.01)

        with tf.variable_scope('rnn'):
            if num_rnn_cells > 1:
                self.rnn = tf.contrib.rnn.MultiRNNCell(
                    [tf.contrib.rnn.BasicLSTMCell(self.s_size) for _ in range(num_rnn_cells)]
                )
            else:
                self.rnn = tf.contrib.rnn.BasicLSTMCell(self.s_size)
            self.rnn_s0 = self.rnn.zero_state(1, tf.float32)

        with tf.variable_scope('rnn_to_rbm'):
            self.Wuh = hp.weight_variables([self.s_size, self.h_size], stddev=0.0001, name='weights_uh')
            self.Wuv = hp.weight_variables([self.s_size, self.v_size], stddev=0.0001, name='weights_uv')
            self.Wqh = hp.weight_variables([self.s_size, self.h_size], stddev=0.0001, name='weights_qh')
            self.Wqv = hp.weight_variables([self.s_size, self.v_size], stddev=0.0001, name='weights_qv')
            self.Buh = hp.bias_variables([self.h_size], value=0.0, name='biases_h')
            self.Buv = hp.bias_variables([self.v_size], value=0.0, name='biases_v')

    def generation_model(self, x, length):
        with tf.variable_scope('generation'):
            primer_state = self.__unroll_rnn(x)
            primer_u, primer_q = primer_state.h[-1], primer_state.c[-1]

        def music_timestep(t, k, x_t, u_tm1, q_tm1, music):
            bh = tf.matmul(u_tm1, self.Wuh) + tf.matmul(q_tm1, self.Wqh) + self.Buh
            bv = tf.matmul(u_tm1, self.Wuv) + tf.matmul(q_tm1, self.Wqv) + self.Buv
            rbm = RBM(self.W, bv, bh)
            notes_t = rbm.gibbs_sample(x_t, 25)
            _, s_t = self.rnn(notes_t, tf.contrib.rnn.LSTMStateTuple(u_tm1, q_tm1))
            music = music + tf.concat([tf.zeros([t, self.v_size]), notes_t,
                                       tf.zeros([k-t-1, self.v_size])], 0)
            return t+1, k, notes_t, u_tm1, s_t.h, s_t.c, music

        count = tf.constant(0)
        music = tf.zeros([length, self.v_size])
        _, _, _, _, _, music = tf.while_loop(lambda t, k, *args: t < k, music_timestep,
                                          [count, length, tf.zeros([1, self.v_size]), primer_u, primer_q, music],
                                          back_prop=False)
        return music

    def train_model(self, x):
        with tf.variable_scope('train_rnn_rbm'):
            states = self.__unroll_rnn(x)
            u_t = tf.reshape(states.h, [-1, self.s_size])
            q_t = tf.reshape(states.c, [-1, self.s_size])
            u_tm1 = tf.concat([self.rnn_s0.h, u_t], 0)[:-1, :]
            q_tm1 = tf.concat([self.rnn_s0.h, q_t], 0)[:-1, :]
            bh = tf.matmul(u_tm1, self.Wuh) + tf.matmul(q_tm1, self.Wqh) + self.Buh
            bv = tf.matmul(u_tm1, self.Wuv) + tf.matmul(q_tm1, self.Wqv) + self.Buv
            rbm = RBM(self.W, bv, bh)

        with tf.variable_scope('train_ops'):
            cost = rbm.free_energy_cost(x, 15)
            cost_summary = tf.summary.scalar('train_cost', cost)
            optimizer = tf.train.GradientDescentOptimizer(learning_rate=0.01)
            gradients = optimizer.compute_gradients(cost)
            gradients = [(tf.clip_by_value(grad, -10.0, 10.0), var) for grad, var in gradients]
            optimizer = optimizer.apply_gradients(gradients)

        return cost, optimizer, cost_summary

    def pretrain_model(self, x):
        with tf.variable_scope('pre-train_rbm'):
            rbm = RBM(self.W, self.Buv, self.Buh)
        with tf.variable_scope('pre-train_ops'):
            cost = rbm.free_energy_cost(x, 1)
            optimizer = tf.train.AdamOptimizer().minimize(cost)
        return cost, optimizer

    def __unroll_rnn(self, x):
        def recurrence(s_tm1, _x):
            _x = tf.reshape(_x, [1, self.v_size])
            _, s_t = self.rnn(_x, s_tm1)
            return s_t
        states = tf.scan(recurrence, x, initializer=self.rnn_s0)
        return states

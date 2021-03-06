import numpy as np

import tensorflow as tf
from nsrec import inputs, test_helper
from nsrec.utils.np_ops import one_hot


class InputTest(tf.test.TestCase):

  def __init__(self, *args):
    super(InputTest, self).__init__(*args)

  def test_batches(self):
    numbers_labels = lambda numbers: np.concatenate(
      [one_hot(np.array(numbers) + 1, 11), np.array([one_hot(11, 11) for _ in range(5 - len(numbers))])])
    max_number_length, expected_length_labels, expected_numbers_labels, expected_numbers_labels_1 = \
        5, one_hot(np.array([2, 2]), 5), numbers_labels([1, 9]), numbers_labels([2, 3])

    data_file_path = test_helper.get_test_metadata()
    batch_size, size = 2, (28, 28)
    with self.test_session() as sess:
      data_batches, length_label_batches, numbers_label_batches = \
        inputs.batches(data_file_path, max_number_length, batch_size, size, num_preprocess_threads=1, channels=3)

      self.assertEqual(data_batches.get_shape(), (2, 28, 28, 3))
      self.assertEqual(length_label_batches.get_shape(), (2, max_number_length))
      self.assertEqual(numbers_label_batches.get_shape(), (2, max_number_length, 11))

      coord = tf.train.Coordinator()
      threads = tf.train.start_queue_runners(sess=sess, coord=coord)

      batches = []
      for i in range(5):
        batches.append(sess.run([data_batches, length_label_batches, numbers_label_batches]))

      db, llb, nlb = batches[0]
      self.assertAllEqual(llb, expected_length_labels)
      self.assertNDArrayNear(nlb[0], expected_numbers_labels, 1e-5)
      self.assertNDArrayNear(nlb[1], expected_numbers_labels_1, 1e-5)

      coord.request_stop()
      coord.join(threads)
      sess.close()

  def test_bbox_batches(self):
    batch_size, size = 2, (28, 28)
    with self.test_session() as sess:
      data_file_path = test_helper.get_test_metadata()
      data_batches, bbox_batches = \
        inputs.bbox_batches(data_file_path, batch_size, size, num_preprocess_threads=1, channels=3)

      self.assertEqual(data_batches.get_shape(), (2, 28, 28, 3))
      self.assertEqual(bbox_batches.get_shape(), (2, 4))

      coord = tf.train.Coordinator()
      threads = tf.train.start_queue_runners(sess=sess, coord=coord)

      # bbox of 1.png: 246, 77, 173, 223, size of 1.png: 741 x 350
      _, bb = sess.run([data_batches, bbox_batches])
      self.assertAllClose(bb[0], [246 / 741, 77 / 350, 173 / 741, 223 / 350])

      coord.request_stop()
      coord.join(threads)
      sess.close()

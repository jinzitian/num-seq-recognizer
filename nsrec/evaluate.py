
"""Evaluate the model.

This script should be run concurrently with training so that summaries show up
in TensorBoard.
"""

import os.path
import time

import math

import tensorflow as tf
from nsrec.models import create_model

FLAGS = tf.flags.FLAGS

current_dir = os.path.dirname(os.path.abspath(__file__))
default_data_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/train.raw.tfrecords')
tf.flags.DEFINE_string("data_file_path", default_data_file_path, "Data file path.")

default_eval_dir = os.path.join(current_dir, '../output/eval')
tf.flags.DEFINE_string("eval_dir", default_eval_dir, "Directory to write event logs.")

tf.flags.DEFINE_integer("eval_interval_secs", 20,
                        "Interval between evaluation runs.")
tf.flags.DEFINE_integer("num_eval_examples", 10132,
                        "Number of examples for evaluation.")

tf.flags.DEFINE_integer("min_global_step", 500,
                        "Minimum global step to run evaluation.")

tf.flags.DEFINE_integer("batch_size", 32, "Batch size.")
tf.flags.DEFINE_integer("num_preprocess_threads", 2, "Number of pre-processor threads")


def evaluate_model(sess, model, global_step, summary_writer, summary_op):
  """
  Args:
    sess: Session object.
    model: Instance of CNNEvalModel; the model to evaluate.
    global_step: Integer; global step of the model checkpoint.
    summary_writer: Instance of SummaryWriter.
    summary_op: Op for generating model summaries.
  """
  # Log model summaries on a single batch.
  summary_str = sess.run(summary_op)
  summary_writer.add_summary(summary_str, global_step)

  # Compute accuracy over the entire dataset.
  num_eval_batches = int(
    math.ceil(FLAGS.num_eval_examples / model.config.batch_size))

  start_time = time.time()
  total_correct_count = 0
  for i in range(num_eval_batches):
    correct_count = model.correct_count(sess)
    total_correct_count += correct_count
    if not i % 10:
      tf.logging.info("Computed accuracy for %d of %d batches: %s",
                      i + 1, num_eval_batches, correct_count / model.config.batch_size)
  eval_time = time.time() - start_time

  accuracy = total_correct_count / (num_eval_batches * model.config.batch_size)
  tf.logging.info("Accuracy = %f (%.2g sec)", accuracy, eval_time)

  # Log accuracy to the SummaryWriter.
  summary = tf.Summary()
  value = summary.value.add()
  value.simple_value = accuracy
  value.tag = "accuracy/eval"
  summary_writer.add_summary(summary, global_step)

  # Write the Events file to the eval directory.
  summary_writer.flush()
  tf.logging.info("Finished processing evaluation at global step %d.",
                  global_step)


def run_once(model, saver, summary_writer, summary_op):
  """Evaluates the latest model checkpoint.

  Args:
    model: Instance of CNNEvalModel; the model to evaluate.
    saver: Instance of tf.train.Saver for restoring model Variables.
    summary_writer: Instance of SummaryWriter.
    summary_op: Op for generating model summaries.
  """
  model_path = tf.train.latest_checkpoint(FLAGS.checkpoint_dir)
  if not model_path:
    tf.logging.info("Skipping evaluation. No checkpoint found in: %s",
                    FLAGS.checkpoint_dir)
    return

  with tf.Session() as sess:
    # Load model from checkpoint.
    tf.logging.info("Loading model from checkpoint: %s", model_path)
    saver.restore(sess, model_path)
    global_step = tf.train.global_step(sess, model.global_step.name)
    tf.logging.info("Successfully loaded %s at global step = %d.",
                    os.path.basename(model_path), global_step)
    if global_step < FLAGS.min_global_step:
      tf.logging.info("Skipping evaluation. Global step = %d < %d", global_step,
                      FLAGS.min_global_step)
      return

    # Start the queue runners.
    coord = tf.train.Coordinator()
    threads = tf.train.start_queue_runners(coord=coord)

    # Run evaluation on the latest checkpoint.
    try:
      evaluate_model(
        sess=sess,
        model=model,
        global_step=global_step,
        summary_writer=summary_writer,
        summary_op=summary_op)
    except Exception as e:  # pylint: disable=broad-except
      tf.logging.error("Evaluation failed.")
      coord.request_stop(e)

    coord.request_stop()
    coord.join(threads, stop_grace_period_secs=10)


def run():
  """Runs evaluation in a loop, and logs summaries to TensorBoard."""
  # Create the evaluation directory if it doesn't exist.
  eval_dir = FLAGS.eval_dir
  if not tf.gfile.IsDirectory(eval_dir):
    tf.logging.info("Creating eval directory: %s", eval_dir)
    tf.gfile.MakeDirs(eval_dir)

  g = tf.Graph()
  with g.as_default(), tf.device('/cpu:0'):
    # Build the model for evaluation.
    model = create_model(FLAGS, 'eval')
    model.build()

    # Create the Saver to restore model Variables.
    saver = tf.train.Saver()

    # Create the summary operation and the summary writer.
    summary_op = tf.summary.merge_all()
    summary_writer = tf.summary.FileWriter(eval_dir)

    g.finalize()

    # Run a new evaluation run every eval_interval_secs.
    while True:
      start = time.time()
      tf.logging.info("Starting evaluation at " + time.strftime(
        "%Y-%m-%d-%H:%M:%S", time.localtime()))
      run_once(model, saver, summary_writer, summary_op)
      time_to_next_eval = start + FLAGS.eval_interval_secs - time.time()
      if time_to_next_eval > 0:
        time.sleep(time_to_next_eval)


def main(unused_argv):
  run()


if __name__ == "__main__":
  tf.app.run()

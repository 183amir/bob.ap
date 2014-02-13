#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Elie Khoury <Elie.Khoury@idiap.ch>
#
# Copyright (C) 2011-2013 Idiap Research Institute, Martigny, Switzerland

import os, sys
import unittest
import bob
import numpy
import array
import math
import time

#############################################################################
# Tests blitz-based extrapolation implementation with values returned
#############################################################################

########################## Values used for the computation ##################
eps = 1e-3

#############################################################################
numpy.set_printoptions(precision=2, threshold=numpy.nan, linewidth=200)

def _read(filename):
  """Read video.FrameContainer containing preprocessed frames"""

  fileName, fileExtension = os.path.splitext(filename)
  wav_filename = filename
  import scipy.io.wavfile
  rate, data = scipy.io.wavfile.read(str(wav_filename)) # the data is read in its native format
  if data.dtype =='int16':
    data = numpy.cast['float'](data)
  return [rate,data]


def compare(v1, v2, width):
  return abs(v1-v2) <= width

def mel_python(f):
  import math
  return 2595.0*math.log10(1.+f/700.0)

def mel_inv_python(value):
  return 700.0 * (10 ** (value / 2595.0) - 1)

def sig_norm(win_length, frame, flag):
  gain = 0.0
  for i in range(win_length):
    gain = gain + frame[i] * frame[i]

  ENERGY_FLOOR = 1.0
  if gain < ENERGY_FLOOR:
    gain = math.log(ENERGY_FLOOR)
  else:
    gain = math.log(gain)

  if(flag and gain != 0.0):
    for i in range(win_length):
      frame[i] = frame[i] / gain
  return gain

def pre_emphasis(frame, win_length, a):
  if (a < 0.0) or (a >= 1.0):
    print("Error: The emphasis coeff. should be between 0 and 1")
  if (a == 0.0):
    return frame
  else:
    for i in range(win_length - 1, 0, -1):
      frame[i] = frame[i] - a * frame[i - 1]
    frame[0] = (1. - a) * frame[0]
  return frame

def hamming_window(vector, hamming_kernel, win_length):
  for i in range(win_length):
    vector[i] = vector[i] * hamming_kernel[i]
  return vector

def log_filter_bank(x, n_filters, p_index, win_size):
  x1 = numpy.array(x, dtype=numpy.complex128)
  complex_ = bob.sp.fft(x1)
  for i in range(0, int(win_size / 2) + 1):
    re = complex_[i].real
    im = complex_[i].imag
    x[i] = math.sqrt(re * re + im * im)
  filters = log_triangular_bank(x, n_filters, p_index)
  return filters, x

def log_triangular_bank(data, n_filters, p_index):
  a = 1.0 / (p_index[1:n_filters+2] - p_index[0:n_filters+1] + 1)
  vec1 =  list(numpy.arange(p_index[i], p_index[i + 1]) for i in range(0, n_filters))
  vec2 =  list(numpy.arange(p_index[i+1], p_index[i + 2] + 1) for i in range(0, n_filters))
  res_ = numpy.array([(numpy.sum(data[vec1[i]]*(1.0 - a [i]* (p_index[i + 1]-(vec1[i])))) +
          numpy.sum(data[vec2[i]] * (1.0 - a[i+1] * ( (vec2[i]) - p_index[i + 1]))))
          for i in range(0, n_filters)])
  FBANK_OUT_FLOOR = 1.0
  filters = numpy.log(numpy.where(res_ < FBANK_OUT_FLOOR, FBANK_OUT_FLOOR, res_))
  return filters

def dct_transform(filters, n_filters, dct_kernel, n_ceps, dct_norm):
  if dct_norm:
    dct_coeff = numpy.sqrt(2.0/(n_filters))
  else :
    dct_coeff = 1.0

  ceps = numpy.zeros(n_ceps + 1)
  vec = numpy.array(range(1, n_filters + 1))
  for i in range(1, n_ceps + 1):
    ceps[i - 1] = numpy.sum(filters[vec - 1] * dct_kernel[i - 1][0:n_filters])
    ceps[i - 1] = ceps[i - 1] * dct_coeff

  return ceps

def spectrogram_computation(obj, rate_wavsample, win_length_ms, win_shift_ms, n_filters, n_ceps, f_min, f_max,
                               pre_emphasis_coef, mel_scale):
  #########################
  ## Initialisation part ##
  #########################

  c = bob.ap.Spectrogram(rate_wavsample[0], win_length_ms, win_shift_ms, n_filters, f_min, f_max, pre_emphasis_coef)

  c.mel_scale = mel_scale

  sf = rate_wavsample[0]
  data = rate_wavsample[1]

  win_length = int (sf * win_length_ms / 1000)
  win_shift = int (sf * win_shift_ms / 1000)
  win_size = int (2.0 ** math.ceil(math.log(win_length) / math.log(2)))
  m = int (math.log(win_size) / math.log(2))

  # Hamming initialisation
  cst = 2 * math.pi / (win_length - 1.0)
  hamming_kernel = numpy.zeros(win_length)

  for i in range(win_length):
    hamming_kernel[i] = (0.54 - 0.46 * math.cos(i * cst))

  # Compute cut-off frequencies
  p_index = numpy.array(numpy.zeros(n_filters + 2), dtype=numpy.int16)
  if(mel_scale):
    # Mel scale
    m_max = mel_python(f_max)

    m_min = mel_python(f_min)

    for i in range(n_filters + 2):
      alpha = ((i) / (n_filters + 1.0))
      f = mel_inv_python(m_min * (1 - alpha) + m_max * alpha)
      factor = f / (sf * 1.0)
      p_index[i] = int (round((win_size) * factor))
  else:
    #linear scale
    for i in range(n_filters + 2):
      alpha = (i) / (n_filters + 1.0)
      f = f_min * (1.0 - alpha) + f_max * alpha
      p_index[i] = int (round((win_size / (sf * 1.0) * f)))

  #Cosine transform initialisation
  dct_kernel = [ [ 0 for i in range(n_filters) ] for j in range(n_ceps) ]

  for i in range(1, n_ceps + 1):
    for j in range(1, n_filters + 1):
      dct_kernel[i - 1][j - 1] = math.cos(math.pi * i * (j - 0.5) / n_filters)

  ######################################
  ### End of the Initialisation part ###
  ######################################

  ######################################
  ###          Core code             ###
  ######################################

  data_size = data.shape[0]
  n_frames = int(1 + (data_size - win_length) / win_shift)

  # create features set
  ceps_sequence = numpy.zeros(n_ceps)
  dim0 = n_ceps
  dim = dim0
  params = [ [ 0 for i in range(dim) ] for j in range(n_frames) ]

  # compute cepstral coefficients
  delta = 0
  for i in range(n_frames):
    # create a frame
    frame = numpy.zeros(win_size, dtype=numpy.float64)
    som = 0.0
    vec = numpy.arange(win_length)
    frame[vec] = data[vec + i * win_shift]
    som = numpy.sum(frame)
    som = som / win_size
    frame = frame - som

    f2 = numpy.copy(frame)

    # pre-emphasis filtering
    frame = pre_emphasis(frame, win_length, pre_emphasis_coef)

    # Hamming windowing
    f2 = numpy.copy(frame)
    frame = hamming_window(frame, hamming_kernel, win_length)


    f2=numpy.copy(frame)
    filters, spec_row = log_filter_bank(frame, n_filters, p_index, win_size)

    vec=numpy.arange(int(win_size/2)+1)

    params[i][0:(int(win_size/2) +1)]=spec_row[vec]
  data = numpy.array(params)

  return data

def spectrogram_comparison_run(obj, rate_wavsample, win_length_ms, win_shift_ms, n_filters, n_ceps, dct_norm, f_min, f_max, delta_win,
                               pre_emphasis_coef, mel_scale):
  c = bob.ap.Spectrogram(rate_wavsample[0], win_length_ms, win_shift_ms, n_filters, f_min, f_max, pre_emphasis_coef, mel_scale)

  A = c(rate_wavsample[1])
  B = spectrogram_computation(obj, rate_wavsample, win_length_ms, win_shift_ms, n_filters, n_ceps,
        f_min, f_max, pre_emphasis_coef, mel_scale)

  diff=numpy.sum(numpy.sum((A-B)*(A-B)))
  obj.assertAlmostEqual(diff, 0., 7, "Error in Ceps Analysis")

##################### Unit Tests ##################
class SpecTest(unittest.TestCase):
  """Test the Spectral feature extraction"""

  def test_spectrogram(self):
    import pkg_resources
    rate_wavsample = _read(pkg_resources.resource_filename(__name__, os.path.join('data', 'sample.wav')))

    win_length_ms = 20
    win_shift_ms = 10
    n_filters = 24
    n_ceps = 19
    f_min = 0.
    f_max = 4000.
    delta_win = 2
    pre_emphasis_coef = 0.97
    dct_norm = True
    mel_scale = True
    spectrogram_comparison_run(self,rate_wavsample, win_length_ms, win_shift_ms, n_filters, n_ceps, dct_norm, f_min, f_max, delta_win,
                               pre_emphasis_coef, mel_scale)


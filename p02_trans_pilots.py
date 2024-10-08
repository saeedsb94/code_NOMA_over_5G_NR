#%%

# Importing the required libraries

import sionna as sn

import numpy as np
import tensorflow as tf
# For the implementation of the Keras models
from tensorflow.keras import Model



# also try %matplotlib widget
import matplotlib.pyplot as plt

# for performance measurements
import time

# Importing the required classes from the sionna library
from sionna.mapping import Constellation, Mapper, Demapper
from sionna.utils import BinarySource, ebnodb2no
from sionna.channel import AWGN
from sionna.utils.metrics import compute_ber
from sionna.signal import Upsampling, Downsampling, RootRaisedCosineFilter, empirical_psd, empirical_aclr
from sionna.nr import PUSCHConfig, PUSCHTransmitter, PUSCHReceiver

# Allow memory growth for GPU
gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)
    
    
print("The required libraries are imported successfully!")
print('sionna version:', sn.__version__)

#%%
# System parameters

# Carrier parameters
numerology = 0 #    Numerology index
num_resource_blocks = 1 # Number of resource blocks
num_slots_per_frame = 2 # Number of slots per frame
num_ofdm_symbols=14

# Transport block parameters
num_bits_per_symbol = 2 # QPSK
coderate = 0.5 # Code rate


# IRSA Parameters
num_frames = 1 # Number of frames
num_replicas_per_frame = 1 # Number of replicas per frame
num_ues=2 # Number of UEs


# Create an instance of needed objects

# Set Resource grid parameters
resource_grid = sn.ofdm.ResourceGrid( num_ofdm_symbols=num_ofdm_symbols,
                                      fft_size=12*num_resource_blocks,# Number of subcarriers
                                      subcarrier_spacing=1e3*(15*2**numerology), # Subcarrier spacing
                                      pilot_pattern="kronecker",
                                      pilot_ofdm_symbol_indices=[0,2]) 


# Binary source
binary_source = sn.utils.BinarySource()

# Encoder
n = int(resource_grid.num_data_symbols*num_bits_per_symbol) # Number of coded bits in a resource grid
k = int(n*coderate) # Number of information bits in a resource groud
encoder = sn.fec.ldpc.LDPC5GEncoder(k, n)

# QAM Mapper
mapper = sn.mapping.Mapper("qam", num_bits_per_symbol)  # maps blocks of information bits to constellation symbols

# Resource grid mapper
resource_grid_mapper = sn.ofdm.ResourceGridMapper(resource_grid)   # maps symbols onto an OFDM resource grid


output_frame = tf.zeros([num_slots_per_frame, resource_grid.num_ofdm_symbols, resource_grid.fft_size], dtype=tf.complex64)
for i in range(num_ues):
    # Generate bits
    bits = binary_source([num_frames, k])
    
    # Encode bits
    codewords = encoder(bits)
    
    # Map codewords to symbols
    symbols = mapper(codewords)
    
    # Map symbols to resource grid  (add two dimensions to the symbols tensor)
    symbols_rg = resource_grid_mapper(tf.expand_dims(tf.expand_dims(symbols, axis=1),axis=1))
    symbols_rg = tf.squeeze(tf.squeeze(symbols_rg, axis=1),axis=1)
    
    # Create a list of unique random indices to select different positions of the replicas
    replicas_indices = np.random.choice(num_slots_per_frame, num_replicas_per_frame, replace=False)
    
    # Print the indices of the replicas for the current UE
    print(f"UE {i+1} replicas indices: {replicas_indices}")
    
    # Create an empty tensor for full frame
    frame_ue = tf.zeros([num_slots_per_frame,resource_grid.num_ofdm_symbols, resource_grid.fft_size], dtype=tf.complex64)
    
    # Scatter the replicas to the empty tensor to form the full frame
    for replica_idx in replicas_indices:
        frame_ue = tf.tensor_scatter_nd_update(frame_ue, [[replica_idx]], symbols_rg)
    
    # add the replicas to the output tensor
    output_frame += frame_ue

# Report
print("Transmission Report:")
print(f"Number of UEs: {num_ues}")
print(f"Number of frames: {num_frames}")
print(f"Number of replicas per frame: {num_replicas_per_frame}")
print(f"Number of slots per frame: {num_slots_per_frame}")
print(f"Resource grid dimensions: {resource_grid.num_ofdm_symbols} OFDM symbols x {resource_grid.fft_size} subcarriers")
print(f"Output frame shape: {output_frame.shape}")


# %%
    # squeeze the output frame
print(f"Output frame shape after squeezing: {output_frame.shape}")

slot=0
rg_ue1=output_frame[slot, :, :]
slot=1
rg_ue2=output_frame[slot, :, :]
pilot_indices = resource_grid._pilot_ofdm_symbol_indices

ue1_pilots= tf.gather(rg_ue1, pilot_indices, axis=0)
print(f"UE1 pilots shape: {ue1_pilots.shape}")
ue2_pilots= tf.gather(rg_ue2, pilot_indices, axis=0)
print(f"UE2 pilots shape: {ue2_pilots.shape}")
original_pilots = tf.squeeze(resource_grid.pilot_pattern.pilots)
print(f"Original pilots shape: {original_pilots.shape}")




#%%
ue1_pilots_fltened = tf.reshape(ue1_pilots, [-1])
ue2_pilots_fltened = tf.reshape(ue2_pilots, [-1])

are_ues_equal=tf.reduce_all(tf.equal(ue1_pilots_fltened,ue2_pilots_fltened))
print("Are the tensors exactly equal? ", are_ues_equal.numpy())

# compare the pilots of the two UEs with the original pilots
are_ues_equal=tf.reduce_all(tf.equal(ue1_pilots_fltened,original_pilots))
print("Are the tensors exactly equal? ", are_ues_equal.numpy())





#%%
resource_grid = sn.ofdm.ResourceGrid( num_ofdm_symbols=14,
                                      fft_size=12*num_resource_blocks,# Number of subcarriers
                                      subcarrier_spacing=1e3*(15*2**numerology), # Subcarrier spacing
                                      num_tx=2,
                                      pilot_pattern="kronecker",
                                      pilot_ofdm_symbol_indices=[0,2]) 
resource_grid.pilot_pattern.show()
pilot=resource_grid.pilot_pattern.pilots



num_bits_per_symbol = 2 # QPSK

binary_source = sn.utils.BinarySource()

mapper = sn.mapping.Mapper("qam", num_bits_per_symbol)

# The resource grid mapper maps symbols onto an OFDM resource grid
rg_mapper = sn.ofdm.ResourceGridMapper(resource_grid)



n = int(resource_grid.num_data_symbols*num_bits_per_symbol) # Number of bits to be transmitted
bits = binary_source([1, resource_grid.num_tx,resource_grid.num_streams_per_tx, n])
symbols = mapper(bits)
symbols_rg = rg_mapper(symbols)
print(f"Resource grid shape: {symbols_rg.shape}")
#%%
symbols_rg = tf.squeeze(symbols_rg)
rg_ue1 = symbols_rg[0, :, :]
rg_ue2 = symbols_rg[1, :, :]
# Plot the resource grid of the two UEs
plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.imshow(np.abs(rg_ue1), aspect='auto')
plt.colorbar()
plt.title('UE1 Resource Grid')
plt.subplot(1, 2, 2)
plt.imshow(np.abs(rg_ue2), aspect='auto')
plt.colorbar()
plt.title('UE2 Resource Grid')
plt.show()


#%%

pusch_config = sn.nr.PUSCHConfig()
dmrs_grid=pusch_config.dmrs_grid
dmrs_grid=tf.squeeze(dmrs_grid)
# plot the DMRS grid
plt.figure(figsize=(10, 5))
plt.imshow(np.abs(dmrs_grid), aspect='auto')
plt.colorbar()
plt.title('DMRS Grid')
plt.show()
pusch_config_1 = pusch_config.clone()
dmrs_grid_1=pusch_config_1.dmrs_grid
dmrs_grid_1=tf.squeeze(dmrs_grid_1)
# plot the DMRS grid
plt.figure(figsize=(10, 5))
plt.imshow(np.abs(dmrs_grid_1), aspect='auto')
plt.colorbar()
plt.title('DMRS Grid')
plt.show()
are_ues_equal=tf.reduce_all(tf.equal(dmrs_grid,dmrs_grid_1))
print("Are the tensors exactly equal? ", are_ues_equal.numpy())

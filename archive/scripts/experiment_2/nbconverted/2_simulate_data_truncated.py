#!/usr/bin/env python
# coding: utf-8

# # Generate truncated simulated data
# 
# Generate simulated data by sampling from VAE latent space.  Then truncate the simulated data to only include some number of dimensions.
# 
# Workflow:
# 1. Input gene expression data from 1 experiment (here we are assuming that there is only biological variation within this experiment)
# 2. Encode this input into a latent space using the trained VAE model
# 3. For each encoded feature, sample from a distribution using the the mean and standard deviation for that feature
# 4. Decode the samples

# In[1]:


get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')

import os
import ast
import pandas as pd
import numpy as np
import random
import glob
import pickle
from keras.models import model_from_json, load_model
from plotnine import *
import umap
import warnings
warnings.filterwarnings(action='ignore')

from numpy.random import seed
randomState = 123
seed(randomState)


# In[2]:


# Load config file
config_file = "config_exp_2.txt"

d = {}
float_params = ["learning_rate", "kappa", "epsilon_std"]
str_params = ["analysis_name", "NN_architecture"]
lst_params = ["num_batches"]
with open(config_file) as f:
    for line in f:
        (name, val) = line.split()
        if name in float_params:
            d[name] = float(val)
        elif name in str_params:
            d[name] = str(val)
        elif name in lst_params:
            d[name] = ast.literal_eval(val)
        else:
            d[name] = int(val)


# In[3]:


# Parameters
num_dims = d["num_dims"]
analysis_name = d["analysis_name"]
NN_architecture = d["NN_architecture"]
num_simulated_samples = d["num_simulated_samples"]


# In[4]:


# Create directories
base_dir = os.path.abspath(os.path.join(os.getcwd(),"../.."))

new_dir = os.path.join(base_dir, "data", "simulated")

analysis_dir = os.path.join(new_dir, analysis_name)

if os.path.exists(analysis_dir):
    print('directory already exists: {}'.format(analysis_dir))
else:
    print('creating new directory: {}'.format(analysis_dir))
os.makedirs(analysis_dir, exist_ok=True)


# In[5]:


# Load arguments
normalized_data_file = os.path.join(
    base_dir,
    "data",
    "input",
    "train_set_normalized.pcl")

metadata_file = os.path.join(
    base_dir,
    "data",
    "metadata",
    "sample_annotations.tsv")

model_encoder_file = glob.glob(os.path.join(
    base_dir,
    "models",
    NN_architecture,
    "*_encoder_model.h5"))[0]

weights_encoder_file = glob.glob(os.path.join(
    base_dir,
    "models",
    NN_architecture,
    "*_encoder_weights.h5"))[0]

model_decoder_file = glob.glob(os.path.join(
    base_dir,
    "models", 
    NN_architecture,
    "*_decoder_model.h5"))[0]


weights_decoder_file = glob.glob(os.path.join(
    base_dir,
    "models",  
    NN_architecture,
    "*_decoder_weights.h5"))[0]

# Saved models
loaded_model = load_model(model_encoder_file)
loaded_decode_model = load_model(model_decoder_file)

loaded_model.load_weights(weights_encoder_file)
loaded_decode_model.load_weights(weights_decoder_file)

# Output
simulated_data_file = os.path.join(
    base_dir,
    "data",
    "simulated",
    analysis_name,
    "simulated_data.txt.xz")

umap_model_file = os.path.join(
    base_dir,
    "models",  
    NN_architecture,
    "umap_model.pkl")


# In[6]:


# Read data
normalized_data = pd.read_table(
    normalized_data_file,
    header=0,
    sep='\t',
    index_col=0).T

print(normalized_data.shape)
normalized_data.head(10)


# ## Plot input data using UMAP

# In[7]:


# UMAP embedding

# Get and save model
model = umap.UMAP(random_state=randomState).fit(normalized_data)
pickle.dump(model, open(umap_model_file, 'wb'))

input_data_UMAPencoded = model.transform(normalized_data)
input_data_UMAPencoded_df = pd.DataFrame(data=input_data_UMAPencoded,
                                         index=normalized_data.index,
                                         columns=['1','2'])


ggplot(input_data_UMAPencoded_df, aes(x='1',y='2'))     + geom_point(alpha=0.5)     + scale_color_brewer(type='qual', palette='Set2')     + ggtitle('Input data')


# ## Plot encoded input data using UMAP

# In[8]:


# Encode data into latent space
data_encoded = loaded_model.predict_on_batch(normalized_data)
data_encoded_df = pd.DataFrame(data_encoded, index=normalized_data.index)

# Plot
latent_data_UMAPencoded = umap.UMAP(random_state=randomState).fit_transform(data_encoded_df)
latent_data_UMAPencoded_df = pd.DataFrame(data=latent_data_UMAPencoded,
                                         index=data_encoded_df.index,
                                         columns=['1','2'])


ggplot(latent_data_UMAPencoded_df, aes(x='1',y='2'))     + geom_point(alpha=0.5)     + scale_color_brewer(type='qual', palette='Set2')     + ggtitle("Encoded input data")


# ## Plot decoded input data using UMAP

# In[9]:


# Decode data back into gene space
data_decoded = loaded_decode_model.predict_on_batch(data_encoded_df)
data_decoded_df = pd.DataFrame(data_decoded, index=data_encoded_df.index)

# Plot
data_decoded_UMAPencoded = model.transform(data_decoded_df)
data_decoded_UMAPencoded_df = pd.DataFrame(data=data_decoded_UMAPencoded,
                                         index=data_decoded_df.index,
                                         columns=['1','2'])


ggplot(data_decoded_UMAPencoded_df, aes(x='1',y='2'))     + geom_point(alpha=0.5)     + scale_color_brewer(type='qual', palette='Set2')     + ggtitle("Decoded input data")


# ## Simulate data
# 
# Generate new simulated data by sampling from the distribution of latent space features.  In other words, for each latent space feature get the mean and standard deviation.  Then we can generate a new sample by sampling from a distribution with this mean and standard deviation.

# In[10]:


# Simulate data

# Encode into latent space
data_encoded = loaded_model.predict_on_batch(normalized_data)
data_encoded_df = pd.DataFrame(data_encoded, index=normalized_data.index)

latent_dim = data_encoded_df.shape[1]

# Get mean and standard deviation per encoded feature
encoded_means = data_encoded_df.mean(axis=0)

encoded_stds = data_encoded_df.std(axis=0)

# Generate samples 
new_data = np.zeros([num_simulated_samples,latent_dim])
for j in range(latent_dim):
    # Use mean and std for feature
    new_data[:,j] = np.random.normal(encoded_means[j], encoded_stds[j], num_simulated_samples) 
    
    # Use standard normal
    #new_data[:,j] = np.random.normal(0, 1, num_simulated_samples)
    
new_data_df = pd.DataFrame(data=new_data)

# Decode N samples
new_data_decoded = loaded_decode_model.predict_on_batch(new_data_df)
simulated_data = pd.DataFrame(data=new_data_decoded)

simulated_data.head(10)


# In[11]:


# Randomly select subset of genes 
subset_simulated_data = simulated_data.sample(n=num_dims, axis=1)
subset_simulated_data.head()


# ## Plot simulated data using UMAP
# 
# Note: we will use the same UMAP mapping for the input and simulated data to ensure they are plotted on the same space.

# In[12]:


# UMAP embedding
simulated_data_UMAPencoded = umap.UMAP(random_state=randomState).fit_transform(subset_simulated_data)
simulated_data_UMAPencoded_df = pd.DataFrame(data=simulated_data_UMAPencoded,
                                         index=simulated_data.index,
                                         columns=['1','2'])


ggplot(simulated_data_UMAPencoded_df, aes(x='1',y='2'))     + geom_point(alpha=0.5)     + scale_color_brewer(type='qual', palette='Set2')     + ggtitle("Simulated data")


# In[13]:


# Output
subset_simulated_data.to_csv(simulated_data_file, sep='\t', compression='xz')


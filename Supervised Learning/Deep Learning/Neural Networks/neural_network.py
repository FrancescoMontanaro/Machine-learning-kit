import re
import numpy as np
from itertools import count
from typing import Callable
from utils import shuffle_data

from layers import _AbstractLayer
from optimizers import _AbstractOptimizer
from loss_functions import _AbstractLossFn


class FeedForwardNeuralNetwork:
    
    ### Static attributes ###
    
    _ids = count(0) # Counter to keep track of the number of NeuralNetwork instances
    
    
    ### Magic methods ###
    
    def __init__(self, layers: list[_AbstractLayer]) -> None:
        """
        Class constructor
        
        Parameters:
        - layers (list[_AbstractLayer]): List of Dense layers
        
        Raises:
        - ValueError: If the layer names are not unique
        """
        
        # List of layers
        self.layers = layers
        self.training = False
        
        # Get the count of how many NeuralNetwork instances have been created
        self.id = next(self._ids)
        
        # Set the name of the layers
        for i, layer in enumerate(self.layers):
            # Set the layer name if it is not set
            if not layer.name:
                # Get the class name of the layer
                layer.name = f"{re.sub(r'(?<!^)(?=[A-Z])', '_', layer.__class__.__name__).lower().lower()}_{i+1}"
                
        # Check if the layers have unique names
        if len(set([layer.name for layer in self.layers])) != len(self.layers):
            raise ValueError("Layer names must be unique!")
        
        
    ### Public methods ###
    
    def set_input_shape(self, batch_size: int, n_features: int) -> None:
        """
        Method to set the input shape of the neural network
        
        Parameters:
        - batch_size (int): Number of samples in each batch
        - n_features (int): Number of features in the input dataset
        
        Raises:
        - ValueError: If the number of layers is 0
        """
        
        # Check if the number of layers is greater than 0
        if len(self.layers) == 0:
            raise ValueError("No layers in the neural network. Add layers to the model!")
        
        # Save the input dimension
        self.input_shape = (batch_size, n_features)
        
        # Iterate over the layers
        for i, layer in enumerate(self.layers):
            # Initialize the parameters of the layer
            layer.set_input_shape(self.input_shape if i == 0 else self.layers[i - 1].output_shape())
      
          
    def fit(
        self, 
        X_train: np.ndarray, 
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        optimizer: _AbstractOptimizer,
        loss_fn: _AbstractLossFn,
        batch_size: int = 8, 
        epochs: int = 10,
        metrics: list[Callable] = []
    ) -> dict[str, dict[str, np.ndarray]]:
        """
        Method to train the neural network
        
        Parameters:
        - X_train (np.ndarray): Features of the training dataset
        - y_train (np.ndarray): Labels of the training dataset
        - X_valid (np.ndarray): Features of the validation dataset
        - y_valid (np.ndarray): Labels of the validation dataset
        - optimizer (_AbstractOptimizer): Optimizer to update the parameters of the model
        - loss_fn (_AbstractLossFn): Loss function to compute the error of the model
        - batch_size (int): Number of samples to use for each batch. Default is 32
        - epochs (int): Number of epochs to train the model. Default is 10
        - metrics (list[Callable]): List of metrics to evaluate the model. Default is an empty list
        
        Returns:
        - dict[str, np.ndarray]: Dictionary containing the training and validation losses
        """
        
        # The input shape must be a 2D array (samples, features) 
        if len(X_train.shape) != 2 or len(X_valid.shape) != 2:
            raise ValueError("The input shape must be a 2D array (samples, features)")
        
        # The output shape must be a 2D array (samples, features)
        if len(y_train.shape) != 2 or len(y_valid.shape) != 2:
            raise ValueError("The output shape must be a 2D array (samples, labels)")
        
        # Initialize the shape of the layers and 
        self.set_input_shape(batch_size=batch_size, n_features=X_train.shape[1])
        
        # Split the dataset into batches
        n_steps = X_train.shape[0] // batch_size if batch_size < X_train.shape[0] else 1
        
        # Initialize the history of the training
        history = {
            "train": {
                "loss": np.array([]),
                "metrics": {metric.__name__: np.array([]) for metric in metrics}
            },
            "valid": {
                "loss": np.array([]),
                "metrics": {metric.__name__: np.array([]) for metric in metrics}
            }
        }
        
        # Iterate over the epochs
        for epoch in range(epochs):
            # Shuffle the dataset
            X_train_shuffled, Y_train_shuffled = shuffle_data(X_train, y_train)
            
            # Set the model in training mode
            self.train()
            
            # Iterate over the batches
            epoch_loss = 0.0
            for step in range(n_steps):
                # Get the current batch
                X_batch = X_train_shuffled[step * batch_size:(step + 1) * batch_size]
                y_batch = Y_train_shuffled[step * batch_size:(step + 1) * batch_size]
                
                # Forward pass: Compute the output of the model
                batch_output = self.forward(X_batch)
                
                # Loss: Compute the error of the model
                loss = loss_fn(y_batch, batch_output)
                
                # Loss gradient: Compute the gradient of the loss with respect to the output of the model
                loss_grad = loss_fn.gradient(y_batch, batch_output)
                
                # Backward pass: Propagate the gradient through the model and update the parameters
                self.backward(loss_grad, optimizer)
                
                # Update the epoch loss
                epoch_loss += loss
                    
            # Set the model in evaluation mode
            self.eval()
            
            # Evaluate the model on the validation set
            validation_output = self.forward(X_valid)
            
            # Store the training and validation losses
            history["train"]["loss"] = np.append(history["train"]["loss"], epoch_loss / (X_train.shape[0] // batch_size))
            history["valid"]["loss"] = np.append(history["valid"]["loss"], loss_fn(y_valid, validation_output))
            
            # Compute the metrics
            for metric in metrics:
                # Compute the metric on the training set and validation set
                train_metric = metric(y_train, self.forward(X_train))
                valid_metric = metric(y_valid, validation_output)
                
                # Store the metrics
                history["train"]["metrics"][metric.__name__] = np.append(history["train"]["metrics"][metric.__name__], train_metric)
                history["valid"]["metrics"][metric.__name__] = np.append(history["valid"]["metrics"][metric.__name__], valid_metric)
            
            # Display progress with metrics
            print(
                f"Epoch {epoch + 1}/{epochs} --> "
                f"Training loss: {history['train']['loss'][-1]:.4f} "
                + " ".join(
                    [f"- Training {metric.__name__.replace("_", " ")}: {history['train']['metrics'][metric.__name__][-1]:.4f}" for metric in metrics]
                )
                + f" | Validation loss: {history['valid']['loss'][-1]:.4f} "
                + " ".join(
                    [f"- Validation {metric.__name__.replace("_", " ")}: {history['valid']['metrics'][metric.__name__][-1]:.4f}" for metric in metrics]
                )
            )
         
        # Return the history of the training   
        return history
        
        
    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass of the neural network
        
        Parameters:
        - x (np.ndarray): Features of the dataset
        
        Returns:
        - np.ndarray: Output of the neural network
        """
        
        # Copy the input
        out = np.copy(x)
        
        # Iterate over the layers
        for layer in self.layers:
            # Compute the output of the layer and pass it to the next one
            out = layer.forward(out)
        
        # Return the output
        return out
    
    
    def backward(self, loss_grad: np.ndarray, optimizer: _AbstractOptimizer) -> np.ndarray:
        """
        Backward pass of the neural network
        
        Parameters:
        - loss_grad (np.ndarray): Gradient of the loss with respect to the output of the neural network
        - optimizer (_AbstractOptimizer): Optimizer to update the parameters of the neural network
        
        Returns:
        - np.ndarray: Gradient of the loss with respect to the input of the neural network
        """
        
        # Iterate over the layers in reverse order
        for layer in reversed(self.layers):
            # Set the layer id for the optimizer to update the parameters
            optimizer.layer_id = layer.get_uuid()
            
            # Compute the gradient of the loss with respect to the input of the layer
            loss_grad = layer.backward(loss_grad, optimizer)
        
        # Return the gradient
        return loss_grad
    
    
    def train(self) -> None:
        """
        Method to set the model in training mode
        """
        
        # Set the training flag to True
        self.training = True
        
        # Iterate over the layers
        for layer in self.layers:
            # Set the layer in training mode
            layer.training = True

        
    def eval(self) -> None:
        """
        Method to set the model in evaluation mode
        """
        
        # Set the training flag to False
        self.training = False
        
        # Iterate over the layers
        for layer in self.layers:
            # Set the layer in evaluation mode
            layer.training = False
            
            
    def summary(self) -> None:
        """
        Method to display the summary of the neural network
        """
        
        def format_output(value: str, width: int) -> str:
            """
            Formats the output to fit within a specified width, splitting lines if necessary.
            
            Parameters:
            - value (str): The value to format
            - width (int): The width of the formatted output in characters
            
            Returns:
            - str: The formatted output
            """
            
            # Split the value by spaces to handle word wrapping
            words = value.split()
            formatted_lines = []
            current_line = ""

            # Iterate over the words
            for word in words:
                # Check if adding the word exceeds the width
                if len(current_line) + len(word) + 1 > width:  # +1 for space
                    # Add the current line to the list of lines
                    formatted_lines.append(current_line)
                    current_line = word
                else:
                    # Add the word to the current line
                    current_line += (" " + word) if current_line else word
            
            # Add the last line
            if current_line:
                formatted_lines.append(current_line)
                
            # Format each line to fit the specified width
            return "\n".join(line.ljust(width) for line in formatted_lines)
        
        # Display the header
        print(f"\nNeural Network (ID: {self.id})\n")
        header = f"{'Layer (type)':<40}{'Output Shape':<20}{'Trainable params #':<20}"
        print(f"{'-' * len(header)}")
        print(header)
        print(f"{'=' * len(header)}")

        # Iterate over the layers
        for idx, layer in enumerate(self.layers):
            # Composing the layer name
            layer_name = f"{layer.name} ({layer.__class__.__name__})"
            
            # Composing the output shape
            output_shape = "?"
            try:
                # Get the output shape of the layer
                output_shape = layer.output_shape() 
                
                # Format the output shape
                output_shape = f"({', '.join(str(dim) for dim in output_shape)})"
            except:
                pass
            
            # Composing the number of parameters
            num_params = "?"
            try:
                # Get the number of parameters of the layer
                num_params = layer.count_params()
            except:
                pass
            
            # format the output
            layer_name = format_output(layer_name, 40)
            output_shape = format_output(str(output_shape), 20)
            num_params = format_output(str(num_params), 20)
            
            # Display the layer information
            print(f"{layer_name:<40}{str(output_shape):<20}{str(num_params):<20}")
            if idx < len(self.layers) - 1 : print(f"{'-' * len(header)}")
            
        # Compute the total number of parameters
        total_params = "?"
        try:
            # Get the total number of parameters
            total_params = sum([layer.count_params() for layer in self.layers])
        except:
            pass
        
        # Display the footer 
        print(f"{'=' * len(header)}")
        print(f"Total trainable parameters: {total_params}")
        print(f"{'-' * len(header)}")
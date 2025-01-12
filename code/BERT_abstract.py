#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoModel, AutoTokenizer, AutoModelForMaskedLM, RobertaForSequenceClassification, \
    RobertaTokenizer, BertTokenizer, BertForSequenceClassification, AdamW
from sklearn.preprocessing import LabelEncoder
import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-l', '--logfile', type=str, help='name of the log file')
parser.add_argument('-tr', '--trainfile', type=str, help='name of the training file')
parser.add_argument('-te', '--testfile', type=str, help='name of the test file')
args = parser.parse_args()


# Define the dataset
# Define the dataset
class Dataset(Dataset):
    def __init__(self, file_paths, label_encoder=None):
        self.data = []
        self.labels = []
        for file_path in file_paths:
            with open(file_path, "r") as f:
                for line in f:
                    text, label = line.strip().split("\t")
                    self.data.append((text, label))
                    self.labels.append(label)

        # if label_encoder is provided, use it. If not, create a new one.
        if label_encoder is None:
            self.label_encoder = LabelEncoder()
            self.label_encoder.fit(self.labels)
        else:
            self.label_encoder = label_encoder

        # Transform labels to integer labels
        for i in range(len(self.data)):
            text, label = self.data[i]
            self.data[i] = (text, self.label_encoder.transform([label])[0])

        # Print out the label mapping
        for i, label in enumerate(self.label_encoder.classes_):
            print(f'{label}: {i}')

    def __getitem__(self, index):
        return self.data[index]

    def __len__(self):
        return len(self.data)

    def get_label_encoder(self):
        return self.label_encoder


time_start = time.time()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
# Load the pre-trained model
# Instantiate the Dataset before trying to access its labels attribute
file_paths = [args.trainfile]
dataset = Dataset(file_paths)
num_labels = len(set(dataset.labels))  # Get number of unique labels
print(num_labels, "labels", set(dataset.labels))
# Then load the model
model = RobertaForSequenceClassification.from_pretrained("allenai/biomed_roberta_base", num_labels=num_labels)
tokenizer = RobertaTokenizer.from_pretrained("allenai/biomed_roberta_base")

# Define the dataloader
file_paths = [args.trainfile]
dataset = Dataset(file_paths)
dataloader = DataLoader(dataset, batch_size=8, shuffle=True)
#
## Fine-tune the model ##
save_model = False
model.train()
num_of_epochs = 8
optimizer = AdamW(model.parameters(), lr=1e-4)  # weight_decay=0.01

with open(args.logfile, 'w') as f:
    print(f"Training for {num_of_epochs} epochs", file=f)
    print(f"Training for {num_of_epochs} epochs")
    for epoch in range(num_of_epochs):
        print(f"Epoch {epoch + 1}/{num_of_epochs}", file=f)
        print(f"Epoch {epoch + 1}/{num_of_epochs}")
        for i, batch in enumerate(dataloader):
            print(f"Batch {i + 1}/{len(dataloader)}", file=f)
            print(f"Batch {i + 1}/{len(dataloader)}")
            texts, labels = batch
            inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
            outputs = model(inputs["input_ids"], inputs["attention_mask"], labels=labels)
            predictions_train = torch.argmax(outputs.logits, dim=1)
            print('Prediction class:', predictions_train, '\tCorrect label:', labels, '\tprobs')
            loss = outputs.loss
            loss.backward()

            optimizer.step()
            optimizer.zero_grad()

    # Define the test dataloader, re-using the label encoder from the training dataset
    test_file_path = [args.testfile]
    test_dataset = Dataset(test_file_path, label_encoder=dataset.get_label_encoder())
    test_dataloader = DataLoader(test_dataset, batch_size=1)

    # Evaluate the model on the test dataset
    model.eval()
    total_correct_preds = 0
    total_samples = 0
    with torch.no_grad():
        for i, batch in enumerate(test_dataloader):
            print(f"Batch {i + 1}/{len(test_dataloader)}", file=f)
            abstract_text, labels = batch
            inputs = tokenizer(abstract_text, padding=True, truncation=True, return_tensors="pt")
            outputs = model(inputs["input_ids"], inputs["attention_mask"])
            predictions = torch.argmax(outputs.logits, dim=1)
            print('Prediction class:', predictions, '\\tCorrect label:', labels, '\\tprobs',
                  torch.nn.functional.softmax(outputs.logits, dim=1).tolist()[0], file=f)
            total_correct_preds += torch.sum(predictions == labels).item()
            total_samples += 1

    accuracy = total_correct_preds / total_samples
    print("Accuracy: {:.2f}%".format(accuracy * 100), file=f)
    time_end = time.time()
    print(f"Time elapsed in this session: {round(time_end - time_start, 2) / 60} minutes", file=f)

# Save the fine-tuned model
if save_model:
    model_dir = f"finetuned_model_roberta_{num_of_epochs}"
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)

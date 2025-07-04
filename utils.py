import torch
import os
import wget
import tarfile
import shutil
import codecs
import youtokentome
import math
from tqdm import tqdm

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def download_data(data_folder):
    """
    Downloads the training, validation, and test files for WMT '14 en-de translation task.

    Training: Europarl v7, Common Crawl, News Commentary v9
    Validation: newstest2013
    Testing: newstest2014

    The homepage for the WMT '14 translation task, https://www.statmt.org/wmt14/translation-task.html, contains links to
    the datasets.

    :param data_folder: the folder where the files will be downloaded

    """
    """ train_urls = ["http://www.statmt.org/wmt13/training-parallel-europarl-v7.tgz",
                  "https://www.statmt.org/wmt13/training-parallel-commoncrawl.tgz",
                  "http://www.statmt.org/wmt14/training-parallel-nc-v9.tgz"]

    print("\n\nThis may take a while.")

    # Create a folder to store downloaded TAR files
    if not os.path.isdir(os.path.join(data_folder, "tar_files")):
        os.mkdir(os.path.join(data_folder, "tar_files"))
    # Create a fresh folder to extract downloaded TAR files; previous extractions deleted to prevent tarfile module errors
    if os.path.isdir(os.path.join(data_folder, "extracted_files")):
        shutil.rmtree(os.path.join(data_folder, "extracted_files"))
        os.mkdir(os.path.join(data_folder, "extracted_files"))

    # Download and extract training data
    for url in train_urls:
        filename = url.split("/")[-1]
        if not os.path.exists(os.path.join(data_folder, "tar_files", filename)):
            print("\nDownloading %s..." % filename)
            wget.download(url, os.path.join(data_folder, "tar_files", filename))
        print("\nExtracting %s..." % filename)
        tar = tarfile.open(os.path.join(data_folder, "tar_files", filename))
        members = [m for m in tar.getmembers() if "de-en" in m.path]
        tar.extractall(os.path.join(data_folder, "extracted_files"), members=members)
    """
    # Download validation and testing data using sacreBLEU since we will be using this library to calculate BLEU scores
    print("\n")
    os.system("sacrebleu -t wmt13 -l en-de --echo src > '" + os.path.join(data_folder, "val.en") + "'")
    os.system("sacrebleu -t wmt13 -l en-de --echo ref > '" + os.path.join(data_folder, "val.de") + "'")
    print("\n")
    os.system("sacrebleu -t wmt14/full -l en-de --echo src > '" + os.path.join(data_folder, "test.en") + "'")
    os.system("sacrebleu -t wmt14/full -l en-de --echo ref > '" + os.path.join(data_folder, "test.de") + "'")

    # Move files if they were extracted into a subdirectory
    for dir in [d for d in os.listdir(os.path.join(data_folder, "extracted_files")) if
                os.path.isdir(os.path.join(data_folder, "extracted_files", d))]:
        for f in os.listdir(os.path.join(data_folder, "extracted_files", dir)):
            shutil.move(os.path.join(data_folder, "extracted_files", dir, f),
                        os.path.join(data_folder, "extracted_files"))
        os.rmdir(os.path.join(data_folder, "extracted_files", dir))


def prepare_data(data_folder, euro_parl=True, common_crawl=False, news_commentary=False, min_length=3, max_length=100,
                 max_length_ratio=1.5, retain_case=True):
    """
    Filters and prepares the training data, trains a Byte-Pair Encoding (BPE) model.

    :param data_folder: the folder where the files were downloaded
    :param euro_parl: include the Europarl v7 dataset in the training data?
    :param common_crawl: include the Common Crawl dataset in the training data?
    :param news_commentary: include theNews Commentary v9 dataset in the training data?
    :param min_length: exclude sequence pairs where one or both are shorter than this minimum BPE length
    :param max_length: exclude sequence pairs where one or both are longer than this maximum BPE length
    :param max_length_ratio: exclude sequence pairs where one is much longer than the other
    :param retain_case: retain case?
    """
    # Read raw files and combine
    slovak = list()
    ukranian = list()
    rusyn = list()
    files = list()
    #assert euro_parl or common_crawl or news_commentary, "Set at least one dataset to True!"
    if euro_parl:
        files.append("CCMatrix.sk-uk")
    """ if common_crawl:
        files.append("commoncrawl.de-en")
    if news_commentary:
        files.append("news-commentary-v9.de-en") """
    print("\nReading extracted_files and combining...")
    for file in files:
        with codecs.open(os.path.join(data_folder, "extracted_files", file + ".sk"), "r", encoding="utf-8") as f:
            if retain_case:
                slovak.extend(f.read().split("\n"))
            else:
                slovak.extend(f.read().lower().split("\n"))
        with codecs.open(os.path.join(data_folder, "extracted_files", file + ".uk"), "r", encoding="utf-8") as f:
            if retain_case:
                ukranian.extend(f.read().split("\n"))
            else:
                ukranian.extend(f.read().lower().split("\n"))
        assert len(ukranian) == len(slovak)

    with codecs.open(os.path.join(data_folder, "extracted_files", "rue_wikipedia_2021_10K-sentences.rue"), "r", encoding="utf-8") as f:
            if retain_case:
                rusyn.extend(f.read().split("\n"))
            else:
                rusyn.extend(f.read().lower().split("\n"))

    # Write to file so stuff can be freed from memory
    print("\nWriting to single files...")
    with codecs.open(os.path.join(data_folder, "train.rue"), "w", encoding="utf-8") as f:
        f.write("\n".join(rusyn))
    with codecs.open(os.path.join(data_folder, "train.sk"), "w", encoding="utf-8") as f:
        f.write("\n".join(ukranian))
    with codecs.open(os.path.join(data_folder, "train.uk"), "w", encoding="utf-8") as f:
        f.write("\n".join(slovak))
    with codecs.open(os.path.join(data_folder, "train.skuk"), "w", encoding="utf-8") as f:
        f.write("\n".join(ukranian + slovak))
    del ukranian, slovak, rusyn  # free some RAM

    # Perform BPE
    print("\nLearning BPE...")
    youtokentome.BPE.train(data=os.path.join(data_folder, "train.skuk"), vocab_size=37000,
                           model=os.path.join(data_folder, "bpe.model"))

    # Load BPE model
    print("\nLoading BPE model...")
    bpe_model = youtokentome.BPE(model=os.path.join(data_folder, "bpe.model"))

    
    # Re-read ukranian, slovak
    print("\nRe-reading single files...")
    with codecs.open(os.path.join(data_folder, "train.sk"), "r", encoding="utf-8") as f:
        ukranian = f.read().split("\n")
    with codecs.open(os.path.join(data_folder, "train.uk"), "r", encoding="utf-8") as f:
        slovak = f.read().split("\n")   

    # Filter
    print("\nFiltering...")
    pairs = list()
    for uk, sk in tqdm(zip(ukranian, slovak), total=len(ukranian)):
        uk_tok = bpe_model.encode(uk, output_type=youtokentome.OutputType.ID)
        sk_tok = bpe_model.encode(sk, output_type=youtokentome.OutputType.ID)
        len_uk_tok = len(uk_tok)
        len_sk_tok = len(sk_tok)
        if min_length < len_uk_tok < max_length and \
                min_length < len_sk_tok < max_length and \
                1. / max_length_ratio <= len_sk_tok / len_uk_tok <= max_length_ratio:
            pairs.append((uk, sk))
        else:
            continue
    print("\nNote: %.2f per cent of en-de pairs were filtered out based on sub-word sequence length limits." % (100. * (
            len(ukranian) - len(pairs)) / len(ukranian)))

    # Rewrite files
    ukranian, slovak = zip(*pairs)
    print("\nRe-writing filtered sentences to single files...")
    os.remove(os.path.join(data_folder, "train.sk"))
    os.remove(os.path.join(data_folder, "train.uk"))
    os.remove(os.path.join(data_folder, "train.skuk"))
    with codecs.open(os.path.join(data_folder, "train.sk"), "w", encoding="utf-8") as f:
        f.write("\n".join(ukranian))
    with codecs.open(os.path.join(data_folder, "train.uk"), "w", encoding="utf-8") as f:
        f.write("\n".join(slovak))
    del ukranian, slovak, bpe_model, pairs

    print("\n...DONE!\n")


def get_positional_encoding(d_model, max_length=100):
    """
    Computes positional encoding as defined in the paper.

    :param d_model: size of vectors throughout the transformer model
    :param max_length: maximum sequence length up to which positional encodings must be calculated
    :return: positional encoding, a tensor of size (1, max_length, d_model)
    """
    positional_encoding = torch.zeros((max_length, d_model))  # (max_length, d_model)
    for i in range(max_length):
        for j in range(d_model):
            if j % 2 == 0:
                positional_encoding[i, j] = math.sin(i / math.pow(10000, j / d_model))
            else:
                positional_encoding[i, j] = math.cos(i / math.pow(10000, (j - 1) / d_model))

    positional_encoding = positional_encoding.unsqueeze(0)  # (1, max_length, d_model)

    return positional_encoding


def get_lr(step, d_model, warmup_steps):
    """
    The LR schedule. This version below is twice the definition in the paper, as used in the official T2T repository.

    :param step: training step number
    :param d_model: size of vectors throughout the transformer model
    :param warmup_steps: number of warmup steps where learning rate is increased linearly; twice the value in the paper, as in the official T2T repo
    :return: updated learning rate
    """
    lr = 2. * math.pow(d_model, -0.5) * min(math.pow(step, -0.5), step * math.pow(warmup_steps, -1.5))

    return lr


def save_checkpoint(epoch, model, optimizer, prefix='models/'):
    """
    Checkpoint saver. Each save overwrites previous save.

    :param epoch: epoch number (0-indexed)
    :param model: transformer model
    :param optimizer: optimized
    :param prefix: checkpoint filename prefix
    """
    state = {'epoch': epoch,
             'model': model,
             'optimizer': optimizer}
    filename = prefix + 'transformer_checkpoint.pth.tar'
    torch.save(state, filename)


def change_lr(optimizer, new_lr):
    """
    Scale learning rate by a specified factor.

    :param optimizer: optimizer whose learning rate must be changed
    :param new_lr: new learning rate
    """
    for param_group in optimizer.param_groups:
        param_group['lr'] = new_lr


class AverageMeter(object):
    """
    Keeps track of most recent, average, sum, and count of a metric.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

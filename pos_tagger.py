from multiprocessing import Pool
import numpy as np
import time
from tagger_utils import *
from math import log
import math

""" Contains the part of speech tagger class. """


def evaluate(data, model):
    """Evaluates the POS model on some sentences and gold tags.

    This model can compute a few different accuracies:
        - whole-sentence accuracy
        - per-token accuracy
        - compare the probabilities computed by different styles of decoding

    You might want to refactor this into several different evaluation functions,
    or you can use it as is. 
    
    As per the write-up, you may find it faster to use multiprocessing (code included). 
    
    """
    processes = 4
    sentences = data[0]
    tags = data[1]
    n = len(sentences)
    k = n//processes
    n_tokens = sum([len(d) for d in sentences])
    unk_n_tokens = sum([1 for s in sentences for w in s if w not in model.word2idx.keys()])
    predictions = {i:None for i in range(n)}
    probabilities = {i:None for i in range(n)}
         
    start = time.time()
    pool = Pool(processes=processes)
    res = []
    for i in range(0, n, k):
        res.append(pool.apply_async(infer_sentences, [model, sentences[i:i+k], i]))
    ans = [r.get(timeout=None) for r in res]
    predictions = dict()
    for a in ans:
        predictions.update(a)
    print(f"Inference Runtime: {(time.time()-start)/60} minutes.")
    
    start = time.time()
    pool = Pool(processes=processes)
    res = []
    for i in range(0, n, k):
        res.append(pool.apply_async(compute_prob, [model, sentences[i:i+k], tags[i:i+k], i]))
    ans = [r.get(timeout=None) for r in res]
    probabilities = dict()
    for a in ans:
        probabilities.update(a)
    
    print(f"Probability Estimation Runtime: {(time.time()-start)/60} minutes.")
    
    token_acc = sum([1 for i in range(n) for j in range(len(sentences[i])) if tags[i][j] == predictions[i][j]]) / n_tokens
    unk_token_acc = sum([1 for i in range(n) for j in range(len(sentences[i])) if tags[i][j] == predictions[i][j] and sentences[i][j] not in model.word2idx.keys()]) / unk_n_tokens
    whole_sent_acc = 0
    num_whole_sent = 0
    for k in range(n):
        sent = sentences[k]
        eos_idxes = indices(sent, '.')
        start_idx = 1
        end_idx = eos_idxes[0]
        for i in range(1, len(eos_idxes)):
            whole_sent_acc += 1 if tags[k][start_idx:end_idx] == predictions[k][start_idx:end_idx] else 0
            num_whole_sent += 1
            start_idx = end_idx+1
            end_idx = eos_idxes[i]
    print("Whole sent acc: {}".format(whole_sent_acc/num_whole_sent))
    print("Mean Probabilities: {}".format(sum(probabilities.values())/n))
    print("Token acc: {}".format(token_acc))
    print("Unk token acc: {}".format(unk_token_acc))
    
    print(len(pos_tagger.tag2idx), len(pos_tagger.idx2tag), len(predictions.values()), len(tags))
    confusion_matrix(pos_tagger.tag2idx, pos_tagger.idx2tag, predictions.values(), tags, 'cm.png')

    return whole_sent_acc/num_whole_sent, token_acc, sum(probabilities.values())/n


class POSTagger():
    def __init__(self):
        """Initializes the tagger model parameters and anything else necessary. """
        
        self.tagCounts = {}
        self.bigramsCount = {}
        self.trigramsCount = {}
        self.emissionsCount = {}
        self.k = 1
    
    
    def get_unigrams(self):
        """
        Computes unigrams. 
        Tip. Map each tag to an integer and store the unigrams in a numpy array. 

        Actually think of this function as a way to get the transition probability 
        Which is basically the probability of a word being a noun or some other tag. 
        So actually need to count the frequency of a certain tag, and divide by the total no of tags. 
        """
        ## TODO
        unigram = np.zeros(len(self.all_tags))
        for tag in self.tag2idx: 
            unigram[self.tag2idx[tag]] = self.tagCounts[tag]/self.N

    def get_bigrams(self):        
        """
        Computes bigrams. 
        Tip. Map each tag to an integer and store the bigrams in a numpy array
             such that bigrams[index[tag1], index[tag2]] = Prob(tag2|tag1). 

        
        So basically this gives you the transition probability of tag2/tag1
        """
        ## TODO

        for tag1 in self.tag2idx: 
            for tag2 in self.tag2idx: 
                self.bigramsCount[(self.tag2idx[tag1], self.tag2idx[tag2])] = 0

        # count the self.bigramsCount
        for sentence in self.data[1]: 
            for i in range(len(sentence)-1): 
                tag1 = sentence[i]
                tag2 = sentence[i+1]
                self.bigramsCount[(self.tag2idx[tag1], self.tag2idx[tag2])] += 1

        # count total bigrams, and use it to divide

        self.bigrams = np.zeros((len(self.all_tags), len(self.all_tags)))
        
        # Implementing add-k smoothing 

        for key, count in self.bigramsCount.items(): 
            tag1 = self.idx2tag[key[0]]
            tag2 = self.idx2tag[key[1]]
            denominator = self.tagCounts[tag1] + self.k*self.N
            self.bigrams[key[0],key[1]] = (count + self.k)/denominator
            
    def get_trigrams(self):
        """
        Computes trigrams. 
        Tip. Similar logic to unigrams and bigrams. Store in numpy array. 
        """
        ## TODO

        # PREPEND ONE EXTRA START : Lecture 4 slide 19

        # Maybe, we will make a 3D np array, with all the possibilities and initialize them to 0. 

        for tag1 in self.tag2idx: 
            for tag2 in self.tag2idx: 
                for tag3 in self.tag2idx:
                    self.trigramsCount[(self.tag2idx[tag1], self.tag2idx[tag2],self.tag2idx[tag3])] = 0

        # Implementing add-k smoothing 
        
        trigrams = np.zeros((len(self.all_tags), len(self.all_tags),len(self.all_tags)))

        for trigram, count in self.trigramsCount.items(): 
            tag1 = self.idx2tag[trigram[0]]
            tag2 = self.idx2tag[trigram[1]]
            tag3 = self.idx2tag[trigram[2]]
            denominator = self.bigramsCount[self.tag2idx[tag1],self.tag2idx[tag2]] + self.k*self.N  # Not sure if this bit is right. 
            trigrams[trigram[0],trigram[1],trigram[2]] = (count + self.k)/denominator

    def get_emissions(self):
        """
        Computes emission probabilities. 
        Tip. Map each tag to an integer and each word in the vocabulary to an integer. 
             Then create a numpy array such that lexical[index(tag), index(word)] = Prob(word|tag) 

        Probability of word given a tag, to find this you need to count instances of the word, given a tag
        """
        ## TODO
        
        for i in range(len(self.data[0])): 
            for j in range(len(self.data[0][i])):
                if (self.data[0][i][j], self.tag2idx[self.data[1][i][j]]) not in self.emissionsCount: 
                    self.emissionsCount[(self.data[0][i][j], self.tag2idx[self.data[1][i][j]])] = 1
                else: 
                    self.emissionsCount[(self.data[0][i][j], self.tag2idx[self.data[1][i][j]])] += 1

        self.emissions = np.zeros((len(self.all_words),len(self.all_tags)))

        for key,value in self.emissionsCount.items():
          
            denom = self.tagCounts[self.idx2tag[key[1]]]
            self.emissions[self.word2idx[key[0]], key[1]] = value/denom


    def train(self, data):
        """Trains the model by computing transition and emission probabilities.

        You should also experiment:
            - smoothing.
            - N-gram models with varying N.
        
        """
        self.data = data  # data[0] has all the words in the data set


        self.all_tags = list(set([t for tag in data[1] for t in tag]))  # This is the list of all the PoS tags in the dataset. 

        self.all_words = list(set([word for sentence in data[0] for word in sentence]))  # This is the list of all the PoS tags in the dataset. 
        self.word2idx = {self.all_words[i]:i for i in range(len(self.all_words))}  # This is basically a dictionary of Tag : id 
        self.idx2word = {v:k for k,v in self.word2idx.items()}    # And this basically is a dictionary of id: Tag


        self.tag2idx = {self.all_tags[i]:i for i in range(len(self.all_tags))}  # This is basically a dictionary of Tag : id 
        self.idx2tag = {v:k for k,v in self.tag2idx.items()}    # And this basically is a dictionary of id: Tag

        ## TODO
        # count of each tag 
        for tag in self.all_tags: 
            self.tagCounts[tag] = 0
        for sentence in data[1]: 
            for tag in sentence: 
                self.tagCounts[tag] += 1

        
        self.N = sum(self.tagCounts.values())
        
        self.get_unigrams()

        self.get_bigrams()

        self.get_trigrams()

        self.get_emissions()


        # Making the assumption that we are starting with bi-grams, n = 2. Can generalise later. 
        # Implement Smoothing -

    def sequence_probability(self, sequence, tags):
        """Computes the probability of a tagged sequence given the emission/transition
        probabilities.
        """
        ## TODO

        prob = 1
        for i in range(1, len(sequence)):
            # probability of word given the tag
            if sequence[i] in self.word2idx:
                q = self.bigrams[self.tag2idx[tags[i-1]], self.tag2idx[tags[i]]]
                e = self.emissions[self.word2idx[sequence[i]], self.tag2idx[tags[i]]]
                prob *= q*e
            else: 
                continue
                # FILL THIS IN 
                # Unknown word prob = 1

        return prob

    def inference(self, sequence):
        """Tags a sequence with part of speech tags.

        You should implement different kinds of inference (suggested as separate
        methods):

            - greedy decoding
            - decoding with beam search
            - viterbi
        """
        # probably won't use this function. 
        ## TODO

        seq = self.greedy(sequence)
        # seq = self.beam(sequence, 2)

        return seq

    def greedy (self, sequence):
        """ Tags a sequence with PoS tags

        Implements Greedy decoding"""

        # ## TODO 
        prev = 'O' # as this is start word
        tagSeq = ['O']
        for word in sequence[1:]: 
            # probability of word given the tag
            maxi = 0
            maxTag = ''

            if word in self.word2idx:
                for tag2 in self.all_tags: 
                    q = self.bigrams[self.tag2idx[prev], self.tag2idx[tag2]]
                    e = self.emissions[self.word2idx[word], self.tag2idx[tag2]]
                    if q*e > maxi: 
                        maxTag = tag2
                        maxi = q*e
                prev = maxTag
                tagSeq.append(maxTag)
            else: 
                # handling the unknown word as a noun
                prev = 'NN'
                tagSeq.append('NN')
        return tagSeq

    def beam(self, sequence, k):
        """ Tags a sequence with PoS tags

        Implements beam search"""

        ## TODO 
        seqs = ['O']
        for word in sequence[1:]: 

            if word in self.word2idx:

                for tag in self.all_tags: 
                
                    q = self.bigrams[self.tag2idx[seq[-1]], self.tag2idx[tag]]









































        # wordOneFlag = True
        # tag_seq = [['O']]
        # tag_seq_prob =  [0]
        # for word in sequence[1:-1]: 
        #     probSet = set()
        #     if word in self.word2idx:
        #         top_prob =  []
        #         top_prob_tags = []

        #         # go through the 3 current sequences we have 
        #         for i in range(len(tag_seq)): 
                
        #             # for each sequence, check each possible tag
        #             for tag2 in self.all_tags: 

        #                 q = self.bigrams[self.tag2idx[tag_seq[i][-1]], self.tag2idx[tag2]]
        #                 e = self.emissions[self.word2idx[word], self.tag2idx[tag2]]
                        
        #                 if e == 0: 
        #                     # print(e)
        #                     continue

        #                 # for each tag for each sequence we have, calculate the product
        #                 prod = log(q) + log(e) + tag_seq_prob[i]
        #                 # print(log(q), log(e))

        #                 # ensure a seq is added only once (unique)
        #                 if prod in probSet:
        #                     break
        #                 probSet.add(prod)
                        
        #                 lowestVal = True

        #                 if len(top_prob) == 0: 
        #                     top_prob.append(prod)
        #                     top_prob_tags.append((tag2, i))

        #                 else: 
        #                     # iterate through the current top 3 probabilities we have stored
        #                     for j in range(len(top_prob)):

        #                         # if the product we have is higher than any of these probabilities
        #                         if prod > top_prob[j]: 
        #                             # if greater than the jth element, then insert in the jth position
        #                             top_prob.insert(j, prod)
        #                             # keep track of the sequence this tag is part of through i
        #                             top_prob_tags.insert(j, (tag2,i))
        #                             if len(top_prob) >= k: 
        #                                 top_prob.pop()
        #                                 top_prob_tags.pop()
        #                             # print(top_prob_tags)
        #                             lowestVal = False
        #                             break
                            
        #                     if lowestVal and len(top_prob) < k: 
        #                         top_prob.append(prod)
        #                         top_prob_tags.append((tag2, i))

        #             print(len(top_prob_tags), top_prob_tags)  
        #             # if wordOneFlag: 
        #             #     wordOneFlag = False
        #             #     break

        #         seqs = [[] for _ in range(len(top_prob))]
        #         probs = [0 for _ in range(len(top_prob))]

        #         for a in range(len(top_prob)):
        #             seqs[a] = tag_seq[top_prob_tags[a][1]]
        #             seqs[a].append(top_prob_tags[a][0])         
        #             probs[a] = tag_seq_prob[top_prob_tags[a][1]]
        #             probs[a] = top_prob[a]         

        #         tag_seq = seqs
        #         tag_seq_prob = probs

        #         # print(word)
        #         # print(tag_seq_prob)

        #     else: # for unknown words, we have assumed prob = 1, and noun
        #         for seq in tag_seq:
        #             seq.append('NN')

        # # print(tag_seq_prob)
        # index = tag_seq_prob.index(max(tag_seq_prob))
        # sol = tag_seq[index]
        # sol.append('.')
        # return sol

    def viterbi (self, sequence):
        """ Tags a sequence with PoS tags

        Implements viterbi decoding"""

        ## TODO 


if __name__ == "__main__":
    pos_tagger = POSTagger()

    train_data = load_data("data/train_x.csv", "data/train_y.csv")
    dev_data = load_data("data/dev_x.csv", "data/dev_y.csv")
    test_data = load_data("data/test_x.csv")

    pos_tagger.train(train_data)

    # Experiment with your decoder using greedy decoding, beam search, viterbi...

    # Here you can also implement experiments that compare different styles of decoding,
    # smoothing, n-grams, etc.
    evaluate(dev_data, pos_tagger)

    # Predict tags for the test set
    test_predictions = []
    for sentence in test_data:
        test_predictions.extend(pos_tagger.inference(sentence))
    
    # Write them to a file to update the leaderboard
    # TODO

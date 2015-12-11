from sklearn import datasets
from sklearn import svm
import shelve

class Learner:
	# Load data from the shelf and perform initial fit
	def __init__(self, load_file):
		if load_file is not None:
			self._data_file = load_file
		else:
			self._data_file = "learner.dat"
			
		self._data = shelve.open(self._data_file, writeback=True)
		if self._data == {}:
			self._data["data"] = []
			self._data["class"] = []
			self._data.sync()
		
		self._svm = svm.SVC(probability=True)		
		if len(self._data["data"]) > 0:
			self._refit()
			
	# Add data and refit
	def train(self, dat, cls):
		self._data["data"].append(dat)
		self._data["class"].append(cls)
		self._data.sync()
		self._refit()
	
	# Provide probability of classifications
	def predict(self, dat):
		return self._svm.predict(dat)
	
	# Helper function for refitting data
	def _refit(self):
		self._svm.fit(self._["data"], self._data["class"])
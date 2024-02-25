#!/usr/bin/env python3

from subprocess import Popen, PIPE, DEVNULL

import sys
import re
import os
import json
import random
import time

if len(sys.argv) < 2:
	print(f"usage: {sys.argv[0]} CONFIG.JSON", file=sys.stderr)
	sys.exit(1)

with open(sys.argv[1]) as f:
	config = json.load(f)


tempdir = "/dev/shm" if os.path.isdir('/dev/shm') else "/tmp"

outfile = tempdir + "/tmp-" + config['name'] + "-conv.txt"

exwords_re = '(' + '|'.join(config['exclude']) + ')' if 'exclude' in config else None

words_count = {}

character_limit = int(config['character_limit']) if 'character_limit' in config else 0
character_minimum = int(config['character_minimum']) if 'character_minimum' in config else 0

for word in config['words']:
	words_count[word] = 0

if os.path.exists(outfile):
	with open(outfile) as f:
		for line in f:
			line = line.rstrip()
			conv_words = re.split(r'[^a-zA-Z0-9]', line)
			for word in conv_words:
				if word in words_count: words_count[word] += 1

prompt = '\n'.join(config['prompt_lines'])

model = os.environ.get('MODEL')
if model is None and 'model' in config:
	model = config['model']
if model is None:
	model = 'llama-2-7b.Q4_K_M.gguf'

random.shuffle(config['words'])

response_must_match = '(' + '|'.join(config['response_must_match']) + ')' if 'respose_must_match' in config else None
response_must_not_match = '(' + '|'.join(config['response_must_not_match']) + ')' if 'response_must_not_match' in config else None

for word in config['words']:
	if words_count[word] > 0:
		print(f"skipping {word}", file=sys.stderr)
		continue
	print(f"processing {word}", file=sys.stderr)
	args = ["./main", "--log-disable", "--escape", "-m", model, "-p", prompt.format(word = word)] + sys.argv[2:]
	p = Popen(args, stdout=PIPE, stderr=DEVNULL, encoding="utf-8")

	lines = []

	start_time = time.time()

	n = 0	
	for line in p.stdout:
		if time.time() - start_time > 5:
			print(f"Timed out on word {word}, skipping...")
			lines = []
			break
		line = line.rstrip()

		print(f"\t\ton line {n}", file=sys.stderr)

		if ( n := n + 1) == 1:
			continue

		if n == 2 and line.find(word) < 0:
			print(f"missing {word} in line {line}", file=sys.stderr)
			lines = []
			break

		if n == 3:
			if response_must_match is not None:
				if not re.search(response_must_match, line):
					print(f"\tdidn't have valid response: {line}", file=sys.stderr)
					lines = []
					break
			if "simple_response" in config:
				m = re.search(r'([,\.\!] could |[,\.\!] can |[,\.] What |[,\.\!] would|, but |, let )', line, re.IGNORECASE)
				if m:
					line = line[:m.start(1)] + '.'
					if line.find('sorry.') > 0:
						print(f"\ttoo short line {line}", file=sys.stderr)
						lines = []
						break
					else:
					    pass
						#print(f"not match {line}", file=sys.stderr)
						#print("reason: bc failed to find sorry. at the end", file=sys.stderr)
				else:
					pass
					#print(f"not match {line}", file=sys.stderr)
			if response_must_not_match is not None:
				if re.search(response_must_not_match, line):
					print(f"\thas invalid response: {line}", file=sys.stderr)
					lines = []
					break
			if character_limit != 0 and len(line) > character_limit:
				print(f"\texceeds character limit ({character_limit}): {line}", file=sys.stderr)
				lines = []
				break
			if character_minimum != 0 and len(line) < character_minimum:
				print(f"\ttoo short a response (less than {character_minimum}): {line}", file=sys.stderr)
				lines = []
				break


		if n >= 4 and "simple_response" in config:
			break

		if line.find(':') < 0:
			print(f"\tending early {word} with: {line}", file=sys.stderr)
			lines = []
			break

		if exwords_re is not None and re.search(exwords_re, line, re.IGNORECASE):
			print(f"\thas excluded word {word}", file=sys.stderr)
			lines = []
			break

		m = re.match(r'(.*): Teacher, ([a-zA-Z])(.*)', line)
		if m:
			line = m.group(1) + ': ' + m.group(2).upper() + m.group(3)

		m = re.match(r'(.*): (?:Excuse me,? )?(?:Teacher|Professor,Miss|Sir|Mister|Mr|Mrs|Ms)\.?(?: *[^ ,]*), ([a-zA-Z])(.*)', line)
		if m:
			line = m.group(1) + ': ' + m.group(2).upper() + m.group(3)

		line = re.sub(r': "([^"]*)"$', r': \1', line)

		lines.append(line)

		words_count[word] += 1
		conv_words = re.split(r'[^a-zA-Z0-9]', line)
		for w in conv_words:
			if w in words_count: words_count[w] += 1

	if len(lines) > 0:
		lines.insert(1, f"TERM: {word}")
		with open(outfile, "a") as f:
			for line in lines:
				print(line, file=sys.stderr)
				print(line, file=f)
			print('', file=f)


with open(outfile) as f:
	for line in f:
		print(line, end='')
os.unlink(outfile)

print("")

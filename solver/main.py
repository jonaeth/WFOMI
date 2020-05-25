from parser import *
from circuit import *
import time
import sys
from statistics import mean


def main():
    partitionFile = sys.argv[1]
    queryFile = sys.argv[2]
    weightFile = sys.argv[3]

    parser = Parser()
    weights, domains = parser.parseWeights(weightFile)
    partitionRoot, partitionNodes = parser.parseCircuit(partitionFile, weights, domains)
    queryRoot, queryNodes = parser.parseCircuit(queryFile, weights, domains)

    startTime = time.time()
    partitionFunc = partitionNodes[partitionRoot].compute().integrate()
    queryFunc = queryNodes[queryRoot].compute().integrate()
    # queryProb = queryFunc / partitionFunc
    queryProb = queryFunc.cst[0] / partitionFunc.cst[0]
    endTime = time.time()
    result_time = endTime - startTime
    print(str(result_time) + ", ", end = '')
    # print(round(mean(time_100), 3))

    print("partition function =", partitionFunc)
    print("the query =", queryFunc)
    print("P(query) =", queryProb)

    # print("time to compute:", endTime - startTime)


if __name__ == "__main__":
    main()

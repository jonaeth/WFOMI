from circuit import *
from sympy.parsing.sympy_parser import parse_expr
import re


class Parser(object):
    def __init__(self):
        self.nodeNumPattern = re.compile('\s*n\d*', re.IGNORECASE)
        self.nodeDataPattern = re.compile('\s*\w*\s*\w*\(*\w*,*\w*\)*', re.IGNORECASE)
        self.linkPattern = re.compile('\s*n\d*\s->', re.IGNORECASE)

        self.connections = {}
        self.reverseConnections = {}
        self.nodes = {}

    def parseCircuit(self, name, weights, domains):
        print("parsing file:", name)

        with open(name) as f:
            content = f.readlines()

        self.connections = {}
        self.reverseConnections = {}
        self.nodes = {}
        constCorrection = []

        self.parseConnections(content)
        self.parseNodes(content, constCorrection, weights, domains)
        self.adjustConstNodes(constCorrection)
          
        root = self.nodeNumPattern.match(content[0]).group().strip()
        self.connectNodes()

        return root, self.nodes


    def parseConnections(self, content):
        for line in content:
            matchLink = self.linkPattern.match(line)
            matchNum = self.nodeNumPattern.match(line)

            # parse the connection line like 'n0 -> n1' else parse the node line
            if matchLink is not None:
                matchData = self.nodeDataPattern.match(line[matchNum.end() + 3:])  # +3 for the _->, space+arrow
                node1 = matchNum.group().strip()
                node2 = matchData.group().strip()
                if node1 not in self.connections:
                    self.connections[node1] = node2
                else:
                    self.connections[node1] = (self.connections[node1], node2)
                self.reverseConnections[node2] = node1

    def parseNodes(self, content, constCorrection, weights, domains):
        for line in content:
            matchLink = self.linkPattern.match(line)
            matchNum = self.nodeNumPattern.match(line)
            
            if matchLink is None:
                matchData = self.nodeDataPattern.match(line[matchNum.end():])
                node = matchNum.group().strip()
                data = matchData.group().strip()
                if data.find("(") != -1:
                    data = data[0:data.find("(")]

                if data == 'C':
                    self.parseConst(line, domains, weights, constCorrection, node)
                else:
                    if data == 'A' or data == 'E':
                        objects, var = self.parseQuantifier(line, domains)
                    else:
                        objects, var = None, None
                    newNode = CreateNewNode(data, var, objects, weights)
                    self.nodes.update({node: newNode})

    def parseQuantifier(self, line, domains):
        var = line[line.find("{") + 1:line.find("}")]
        without = []
        domainFull = line[line.find("}") + 2:-2]
                    
        if len(domainFull.split("/")) > 1:
            domainSet, without = domainFull.split("/")
            domainSet, without = domainSet.split(","), without.split(",")
        else:
            domainSet = line[line.find("}") + 2:-2].split(",")
            
        domainType = ""
        if len(domainSet[0].split("-")) > 1:
            domainSet, domainType = domainSet[0].split("-")
            domainSet = [domainSet]

        objects = {}
        objects.update({var: (domains[domainSet[0]], domainType, without, domainFull)})
        return objects, var

    def parseConst(self, line, domains, weights, constCorrection, node):
        varSet = line[line.find("{") + 1:line.find("}")].split(",")
        line = line[line.find("}") + 2:]
        doms = line[0:line.find("}")].split(",")
        objects = {}
        without = []
        domainSet = []
        domainTypeSet = []
        withoutSet = []

        for dom in doms:
            if len(dom.split("/")) > 1:
                domainType, without = dom.split("/")
                without = without.split("+")
                withoutSet.append(without)
                if len(domainType.split("-")) > 1:
                    d, domainType = domainType.split("-")
                    domainSet.append(d)
                else:
                    domainSet.append(domainType)
                domainTypeSet.append(domainType)
            else:
                if len(dom.split("-")) > 1:
                    d, domainType = dom.split("-")
                    domainSet.append(d)
                    domainTypeSet.append(domainType)
                else:
                    d = dom.split(",")
                    domainSet.append(d[0])
                    domainTypeSet.append("")
                withoutSet.append("")

        for dom, var, domType, without in zip(domainSet, varSet, domainTypeSet, withoutSet):
            objects.update({node + var: (domains[dom.strip()], domType, without)})

        line = line[line.find("}") + 2:]
        if line.find("or") != -1 or line.find("and") != -1:
            if line.find("or") != -1:
                leftData, rightData = line.split("or")
                mainNode = ConstantNode("or", node, varSet, objects)
            else:
                leftData, rightData = line.split("and")
                mainNode = ConstantNode("and", node, varSet, objects)
            leftData = leftData.lower().strip()
            rightData = rightData.lower().strip()
            leftData = leftData[0:leftData.find('(')]
            rightData = rightData[0:rightData.find('(')]
            leftNode = LeafNode(leftData, weights)
            rightNode = LeafNode(rightData, weights)
            leftName = node + "a"
            rightName = node + "b"
            
            self.nodes.update({leftName: leftNode})
            self.nodes.update({rightName: rightNode})
            self.nodes.update({node: mainNode})
            self.connections.update({node: (leftName, rightName)})
        else:
            leftData = line.lower().strip()
            leftData = leftData[0:leftData.find('(')]
            leftNode = LeafNode(leftData, weights)
            leftName = node + "a"
            mainNode = ConstantNode("leaf", node, varSet, objects)
            self.nodes.update({leftName: leftNode})
            self.nodes.update({node: mainNode})
            self.connections.update({node: leftName})

        if len(varSet) == 1 and len(weights.get(leftData)) > 3:
            constCorrection.append([doms[0], node])
    
    def adjustConstNodes(self, constCorrection):
        for constDom, constNode in constCorrection:
            nextForAllNode = self.nextMatchingForAll(self.reverseConnections[constNode], constDom)
            if nextForAllNode is not None and not self.ancestorIsForAll(nextForAllNode):
                # print(nextForAllNode, constNode, constDom, nodes[nextForAllNode].objects[nodes[nextForAllNode].var][3])
                forAllChild = self.connections[nextForAllNode]
                constParent = self.reverseConnections[constNode]
                constGrandParent = self.reverseConnections[constParent]
                    
                parentSibling = None
                if self.connections[constGrandParent] != constParent:
                    parentSibling = (set(self.connections[constGrandParent]) - set([constParent])).pop()
                    constSibling = None
                if self.connections[constParent] != constNode:
                    constSibling = (set(self.connections[constParent]) - set([constNode])).pop()
                        
                self.connections.update({nextForAllNode: constParent})
                self.connections.update({constParent: (constNode, forAllChild)})
                if parentSibling is not None and constSibling is not None:
                    self.connections.update({constGrandParent: (parentSibling, constSibling)})
                    self.reverseConnections.update({parentSibling: constGrandParent})
                    self.reverseConnections.update({constSibling: constGrandParent})
                elif parentSibling is None:
                    self.connections.update({constGrandParent: constSibling})
                    self.reverseConnections.update({constSibling: constGrandParent})
                elif constSibling is None:
                    self.connections.update({constGrandParent: parentSibling})
                    self.reverseConnections.update({parentSibling: constGrandParent})
                        
                    self.reverseConnections.update({constParent: nextForAllNode})
                    self.reverseConnections.update({constNode: constParent})
                    self.reverseConnections.update({forAllChild: constParent})
                    
                self.nodes[constNode].shouldIntegrate = False

    
    # parse weights file.
    # In the weights file there can be 3 types of lines:
    # the domain line eg. 'person = {Alice}'
    # the simple weight line eg. 'pre: [1, 10]', meaning the predicate pre is assigned weight 1 and its negation is assigned weight 10
    # the complex weight line eg. 'bmi(x)fun x**2 + 10 bounds[5, 10]'
    # note that for complex weights the negation weight has to be specified seperately eg. 'neg bmi(x)fun x**2 + 10 bounds[10, 20]'
    # IMPORTANT - the name of the arguments of the weight functions must correspond to the argument names used in the circuit description 
    def parseWeights(self, name):
        # print("parsing file:", name)

        with open(name) as f:
            content = f.readlines()

        weights = {}
        domains = {}
        for line in content:
            function = domain = ""
            weight = objects = []

            # if line contains '=' it must be the domain line, parse it accordingly
            if line.find("=") != -1:
                domain = line[0:line.find("=") - 1]
                objects = line[line.find("{") + 1:line.find("}")].split(",")
                domains.update({domain: objects})
            # if line contains ':' it must be the simple weight line
            elif line.find(":") != -1:
                function = line[0:line.find(":")]
                weight = line[line.find("[") + 1:line.find("]")].split(",")
                const = [1, 1]
                if line.find('const') != -1:
                    const = line[line.find('const')+6:-2].split(",")
                weights.update({function: (float(weight[0]), float(const[0]))})
                weights.update({"neg " + function: (float(weight[1]), float(const[1]))})
            # if line contains 'fun' it must be the complex weight line
            elif line.find("fun") != -1:
                function = line[0:line.find("fun")]
                if function.find('(') != -1:
                    function = function[0:function.find('(')]
                args = line[line.find('(') + 1:line.find(')')].split(",")
                if line.find("bounds") != -1:
                    weight = parse_expr(line[line.find("fun")+4:line.find("bounds")])
                    bounds = list(line[line.find("[") + 1:line.find("]")].split(","))
                    it = iter(bounds)
                    bounds = list(zip(it, it))
                    const = 1
                    if line.find('const') != -1:
                        const = line[line.find('const')+6:-2]
                    weights.update({function: (weight, bounds, args, const)})
                else:
                    if line.find('const') != -1:
                        weight = parse_expr(line[line.find("fun")+4:line.find("const")])
                        const = line[line.find('const')+6:-2]
                    else:
                        weight = parse_expr(line[line.find("fun")+4:])
                    weights.update({function: (weight, float(const))})

        return weights, domains

    def connectNodes(self):
        for node in self.connections.keys():
            if type(self.connections[node]) is tuple:
                self.nodes[node].left = self.nodes[self.connections[node][0]]
                self.nodes[node].right = self.nodes[self.connections[node][1]]
            else:
                self.nodes[node].left = self.nodes[self.connections[node]]

    def ancestorIsForAll(self, node):
        if node not in self.reverseConnections:
            return None
        if type(self.nodes[self.reverseConnections[node]]) is ForAllNode:
            return self.reverseConnections[node]
        else:
            return self.ancestorIsForAll(self.reverseConnections[node])


    def nextMatchingForAll(self, node, domain):
        if type(self.nodes[node]) is ForAllNode and self.nodes[node].objects[self.nodes[node].var][3] == domain:
            return node
        elif type(self.nodes[node]) is not ConstantNode:
            if node in self.connections and type(self.connections[node]) is tuple:
                result0 = self.nextMatchingForAll(self.connections[node][0], domain)
                result1 = self.nextMatchingForAll(self.connections[node][1], domain)
                if result0 is None:
                    return result1
                else:
                    return result0
            elif node in self.connections:
                return self.nextMatchingForAll(self.connections[node], domain)

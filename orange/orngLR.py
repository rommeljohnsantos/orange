import orange
import orngCI
import math, os
from Numeric import *
from LinearAlgebra import *


#######################
## Print out methods ##
#######################

def printOUT(classifier):
    # print out class values
    print
    print "class attribute = " + classifier.domain.classVar.name
    print "class values = " + str(classifier.domain.classVar.values)
    print
    
    # get the longest attribute name
    longest=0
    for at in classifier.domain.attributes:
        if len(at.name)>longest:
            longest=len(at.name);

    # print out the head
    formatstr = "%"+str(longest)+"s %10s %10s %10s %10s"
    print formatstr % ("Attribute", "beta", "st. error", "wald Z", "P")
    print
    formatstr = "%"+str(longest)+"s %10.2f %10.2f %10.2f %10.2f"    
    print formatstr % ("Intercept", classifier.beta[0], classifier.beta_se[0], classifier.wald_Z[0], classifier.P[0])
    for i in range(len(classifier.domain.attributes)):
        print formatstr % (classifier.domain.attributes[i].name, classifier.beta[i+1], classifier.beta_se[i+1], classifier.wald_Z[i+1], abs(classifier.P[i+1]))
        


##########################
## LEARNER improvements ##
##########################
#construct "continuous" attributes from discrete attributes
def createNoDiscDomain(domain):
    attributes = []
    #iterate through domain
    for at in domain.attributes:
        #if att is discrete, create (numOfValues)-1 new ones and set getValueFrom
        if at.varType == orange.VarTypes.Discrete:
            for ival in range(len(at.values)):
                # continue at first value 
                if ival == 0:
                    continue
                # create attribute
                newVar = orange.FloatVariable(at.name+"="+at.values[ival])
                
                # create classifier
                vals = [orange.Value((float)(ival==i)) for i in range(len(at.values))]
                vals.append("?")
                #print (vals)
                cl = orange.ClassifierByLookupTable(newVar, at, vals)                
                newVar.getValueFrom=cl

                # append newVariable                
                attributes.append(newVar)
        else:
            # add original attribute
            attributes.append(at)
    attributes.append(domain.classVar)
    return orange.Domain(attributes)
                
# returns data set without discrete values. 
def createNoDiscTable(olddata):
    newdomain = createNoDiscDomain(olddata.domain)
    #print newdomain
    return olddata.select(newdomain)

def hasDiscreteValues(domain):
    for at in domain.attributes:
        if at.varType == orange.VarTypes.Discrete:
            return 1
    return 0

def LogisticLearner(examples = None, weightID=0, **kwds):
    lr = LogisticLearnerClass(**kwds)
    if examples:
        return lr(examples, weightID)
    else:
        return lr

class LogisticLearnerClass:
    def __init__(self, removeSingular=0, showSingularity=1, **kwds):
        self.__dict__ = kwds
        self.removeSingular = removeSingular
        self.showSingularity = showSingularity
    def __call__(self, examples, weight=0):
        if hasDiscreteValues(examples.domain):
            nexamples = createNoDiscTable(examples)
        else:
            nexamples = examples

        
        if self.removeSingular:
            lr = orange.LogisticLearner(nexamples, weight, showSingularity = not self.removeSingular)
        else:
            lr = orange.LogisticLearner(nexamples, weight, showSingularity = self.showSingularity)
        while (lr.error == 6 or lr.error == 5) and self.removeSingular == 1:
            print "removing " + lr.error_att.name
            nexamples.domain.attributes.remove(lr.error_att)
            nexamples = nexamples.select(orange.Domain(nexamples.domain.attributes, nexamples.domain.classVar))
            if self.removeSingular:
                lr = orange.LogisticLearner(nexamples, weight, showSingularity = not self.removeSingular)
            else:
                lr = orange.LogisticLearner(nexamples, weight, showSingularity = self.showSingularity)
        return lr


######################################
#### Fitters for logistic learner ####
######################################

def Pr(x, betas):
    k = math.exp(dot(x, betas))
    return k / (1+k)

def lh(x,y,betas):
    return 0

class simpleFitter(orange.LogisticFitter):
    def __init__(self, penalty=0):
        self.penalty = penalty
    def __call__(self, data, weight=0):
        ml = data.native(0)
        for i in range(len(data.domain.attributes)):
          a = data.domain.attributes[i]
          if a.varType == orange.VarTypes.Discrete:
            for m in ml:
              m[i] = a.values.index(m[i])
        for m in ml:
          m[-1] = data.domain.classVar.values.index(m[-1])

        Xtmp = array(ml)
        y = Xtmp[:,-1]   # true probabilities (1's or 0's)
        one = reshape(array([1]*len(data)), (len(data),1)) # intercept column
        X=concatenate((one, Xtmp[:,:-1]),1)  # intercept first, then data

        betas = array([0.0] * (len(data.domain.attributes)+1))

# predict the probability for an instance, x and betas are vectors


# start the computation

        N = len(data)
        for i in range(20):
            p = array([Pr(X[i], betas) for i in range(len(data))])

            W = identity(len(data), Float)
            pp = p * (1.0-p)
            for i in range(N):
                W[i,i] = pp[i]

            WI = inverse(W)
            z = matrixmultiply(X, betas) + matrixmultiply(WI, y - p)

            tmpA = inverse(matrixmultiply(transpose(X), matrixmultiply(W, X))+self.penalty*identity(len(data.domain.attributes)+1, Float))
            tmpB = matrixmultiply(transpose(X), matrixmultiply(W, z))
            betas = matrixmultiply(tmpA, tmpB)
            likelihood_new = lh(X,y,betas)
            #if abs(likelihood_new-likelihood)<0.001:
            #    break
            likelihood = likelihood_new
            
        XX = sqrt(diagonal(inverse(matrixmultiply(transpose(X),X))))
        yhat = array([Pr(X[i], betas) for i in range(len(data))])
        ss = sum((y - yhat) ** 2) / (N - len(data.domain.attributes) - 1)
        sigma = math.sqrt(ss)
        beta = []
        for i in range(len(betas)):
            beta.append(betas[i])        
        return (self.OK, beta, [sigma], 0)




    
############################################################
####  Feature subset selection for logistic regression  ####
############################################################


def StepWiseFSS(examples = None, **kwds):
    """
      Constructs and returns a new set of examples that includes a
      class and attributes selected by stepwise logistic regression. This is an
      implementation of algorithm described in [Hosmer and Lemeshow, Applied Logistic Regression, 2000]

      examples: data set (ExampleTable)     
      addCrit: "Alpha" level to judge if variable has enough importance to be added in the new set. (e.g. if addCrit is 0.2, then attribute is added if its P is lower than 0.2)
      deleteCrit: Similar to addCrit, just that it is used at backward elimination. It should be higher than addCrit!
      numAttr: maximum number of selected attributes, use -1 for infinity
    """

    fss = apply(StepWiseFSS_class, (), kwds)
    if examples:
        return fss(examples)
    else:
        return fss


class StepWiseFSS_class:
  def __init__(self, addCrit=0.2, deleteCrit=0.3, numAttr = -1):
    self.addCrit = addCrit
    self.deleteCrit = deleteCrit
    self.numAttr = numAttr
  def __call__(self, examples):
    attr = []
    # TODO: kako v enem koraku premaknes vse v remain_attr?    
    remain_attr = []
    for at in examples.domain.attributes:
        remain_attr.append(at)

    
    # get LL for Majority Learner 
    tempDomain = orange.Domain(attr,examples.domain.classVar)
    ll_Old = LogisticLearner(examples.select(tempDomain)).likelihood;

    
    stop = 0
    while not stop:
        # LOOP until all variables are added or no further deletion nor addition of attribute is possible
        
        # if there are more than 1 attribute then perform backward elimination
        if len(attr) >= 2:
            maxG = -1
            worstAt = attr[0]
            ll_Best = ll_Old
            for at in attr:
                # check all attribute whether its presence enough increases LL?

                # TU SPET, KAKO KOPIRAS?
                tempAttr = []
                for at_tmp in attr:
                    if at_tmp != at:
                        tempAttr.append(at_tmp)

                
                tempDomain = orange.Domain(tempAttr,examples.domain.classVar)
                # domain, calculate P for LL improvement.
                ll_Delete = LogisticLearner(examples.select(tempDomain), showSingularity = 0).likelihood;
                # P=PR(CHI^2>G), G=-2(L(0)-L(1))=2(E(0)-E(1))
                G=-2*(ll_Old-ll_Delete);

                # set new best attribute                
                if G>maxG:
                    worstAt = at
                    maxG=G
                    ll_Best = ll_Delete
            # deletion of attribute
            if worstAt.varType==orange.VarTypes.Continuous:
                P=lchisqprob(maxG,1);
            else:
                P=lchisqprob(maxG,len(worstAt.values)-1);
            if P<=self.deleteCrit:
                print "Deleting: "
                print worstAt
                attr.remove(worstAt)
                remain_attr.append(worstAt)
                nodeletion=0
                ll_Old = ll_Best
            else:
                nodeletion=1
        else:
            nodeletion = 1
            # END OF DELETION PART
            
        # if enough attributes has been chosen, stop the procedure
        if self.numAttr>-1 and len(attr)>=self.numAttr:
            remain_attr=[]
         
        # for each attribute in the remaining
        maxG=-1
        ll_Best = ll_Old
        for at in remain_attr:
            tempAttr = attr + [at]
            tempDomain = orange.Domain(tempAttr,examples.domain.classVar)
            # domain, calculate P for LL improvement.
            ll_New = LogisticLearner(examples.select(tempDomain), showSingularity = 0).likelihood;
            # P=PR(CHI^2>G), G=-2(L(0)-L(1))=2(E(0)-E(1))
            G=-2*(ll_Old-ll_New);
            if G>maxG:
                bestAt = at
                maxG=G
                ll_Best = ll_New

        if bestAt.varType==orange.VarTypes.Continuous:
            P=lchisqprob(maxG,1);
        else:
            P=lchisqprob(maxG,len(bestAt.values)-1);

        print P
        # Add attribute with smallest P to attributes(attr)
        if P<=self.addCrit:
            attr.append(bestAt)
            remain_attr.remove(bestAt)
            ll_Old = ll_Best

        if P>self.addCrit and nodeletion:
            stop = 1

    #print "Likelihood is:"
    #print ll_Old
    #return examples.select(orange.Domain(attr,examples.domain.classVar))
    return attr


def StepWiseFSS_Filter(examples = None, **kwds):
    """
        check function StepWiseFSS()
    """

    filter = apply(StepWiseFSS_Filter_class, (), kwds)
    if examples:
        return filter(examples)
    else:
        return filter


class StepWiseFSS_Filter_class:
    def __init__(self, addCrit=0.2, deleteCrit=0.3, numAttr = -1):
        self.addCrit = addCrit
        self.deleteCrit = deleteCrit
        self.numAttr = numAttr
    def __call__(self, examples):
        attr = StepWiseFSS(examples, addCrit=self.addCrit, deleteCrit = self.deleteCrit, numAttr = self.numAttr)
        return examples.select(orange.Domain(attr, examples.domain.classVar))
                

####################################
####  PROBABILITY CALCULATIONS  ####
####################################

def lchisqprob(chisq,df):
    """
Returns the (1-tailed) probability value associated with the provided
chi-square value and df.  Adapted from chisq.c in Gary Perlman's |Stat.

Usage:   lchisqprob(chisq,df)
"""
    BIG = 20.0
    def ex(x):
    	BIG = 20.0
    	if x < -BIG:
    	    return 0.0
    	else:
    	    return math.exp(x)
    if chisq <=0 or df < 1:
    	return 1.0
    a = 0.5 * chisq
    if df%2 == 0:
    	even = 1
    else:
    	even = 0
    if df > 1:
    	y = ex(-a)
    if even:
    	s = y
    else:
        s = 2.0 * zprob(-math.sqrt(chisq))
    if (df > 2):
        chisq = 0.5 * (df - 1.0)
        if even:
            z = 1.0
        else:
            z = 0.5
        if a > BIG:
            if even:
            	e = 0.0
            else:
            	e = math.log(math.sqrt(math.pi))
            c = math.log(a)
            while (z <= chisq):
            	e = math.log(z) + e
            	s = s + ex(c*z-a-e)
            	z = z + 1.0
            return s
        else:
            if even:
                e = 1.0
            else:
                e = 1.0 / math.sqrt(math.pi) / math.sqrt(a)
    		c = 0.0
    		while (z <= chisq):
    		    e = e * (a/float(z))
    		    c = c + e
    		    z = z + 1.0
    		return (c*y+s)
    else:
    	return s


def zprob(z):
    """
Returns the area under the normal curve 'to the left of' the given z value.
Thus, 
    for z<0, zprob(z) = 1-tail probability
    for z>0, 1.0-zprob(z) = 1-tail probability
    for any z, 2.0*(1.0-zprob(abs(z))) = 2-tail probability
Adapted from z.c in Gary Perlman's |Stat.

Usage:   lzprob(z)
"""
    Z_MAX = 6.0    # maximum meaningful z-value
    if z == 0.0:
	x = 0.0
    else:
	y = 0.5 * math.fabs(z)
	if y >= (Z_MAX*0.5):
	    x = 1.0
	elif (y < 1.0):
	    w = y*y
	    x = ((((((((0.000124818987 * w
			-0.001075204047) * w +0.005198775019) * w
		      -0.019198292004) * w +0.059054035642) * w
		    -0.151968751364) * w +0.319152932694) * w
		  -0.531923007300) * w +0.797884560593) * y * 2.0
	else:
	    y = y - 2.0
	    x = (((((((((((((-0.000045255659 * y
			     +0.000152529290) * y -0.000019538132) * y
			   -0.000676904986) * y +0.001390604284) * y
			 -0.000794620820) * y -0.002034254874) * y
		       +0.006549791214) * y -0.010557625006) * y
		     +0.011630447319) * y -0.009279453341) * y
		   +0.005353579108) * y -0.002141268741) * y
		 +0.000535310849) * y +0.999936657524
    if z > 0.0:
	prob = ((x+1.0)*0.5)
    else:
	prob = ((1.0-x)*0.5)
    return prob

   
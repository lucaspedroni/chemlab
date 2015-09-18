"""Topology handling in gromacs"""
from ..db import ChemlabDB
from ..core import System, Molecule, Atom
import itertools

db = ChemlabDB()

_symbols = db.get('data', 'symbols')
_weight = db.get('data', 'massdict')

def atomic_no(atom):
    return _symbols.index(atom)

def atomic_weight(atom):
    return _weight[atom]

def line(*args, **kwargs):
    kwargs.get("just", "right")
    if just == "right":
        return ''.join(str(a).rjust(10) for a in args) + '\n'
    if just == "left":
        return ''.join(str(a).ljust(10) for a in args) + '\n'
    else:
        raise ValueError('just must be right or left')
def comment(*args):
    return ';' + line(*args)

class ChargedLJ(object):
    
    def __init__(self, name, q, type, sigma, eps):
        self.name = name
        self.q = q
        self.type = type
        self.sigma = sigma
        self.eps = eps

class InterMolecular(object):
    
    def __init__(self):
        self.particles = []

    @classmethod
    def from_dict(cls, data):
        self = cls()
        for name, atomspec in data.items():
            particle = ChargedLJ(name, atomspec['q'], atomspec['type'], atomspec['sigma'], atomspec['eps'])
            self.particles.append(particle)
        return self
    
    @property
    def pairs(self):
        pairs = []
        for i, j in itertools.combinations(self.particles, 2):
            sigma, eps = combine_lorentz_berthelot(i.sigma, j.sigma, i.eps, j.eps)
            pairs.append(PairInteraction((i.name, j.name), sigma, eps))
        return pairs

def combine_lorentz_berthelot(sigma1, sigma2, eps1, eps2):
    return (sigma1 + sigma2)/2, (eps1*eps2)**0.5

class PairInteraction:
    def __init__(self, pair, sigma, eps):
        self.pair = pair
        self.sigma = sigma
        self.eps = eps
        
    
    
    
class MolecularConstraints:
    
    def __init__(self, name, bonds, angles, dihedrals):
        self.name = name
        self.bonds = bonds
        self.angles = angles
        self.dihedrals = dihedrals
    
class HarmonicConstraint:
    
    def __init__(self, between, r, k):
        self.between = between
        self.r = r
        self.k = k

class HarmonicAngleConstraint:
    
    def __init__(self, between, theta, k):
        self.between = between
        self.theta = theta
        self.k = k

class IntraMolecular(object):
    def __init__(self):
        self.molecules = []
    
    @classmethod
    def from_dict(cls, data):
        self = cls()
        for name, molspec in data.items():
            
            if 'bonds' in molspec:
                bonds = [HarmonicConstraint(b['between'], b['r'], b['k']) 
                          for b in molspec['bonds']]
            else:
                bonds = []
            
            if 'angles' in molspec:
                angles = [HarmonicAngleConstraint(b['between'], b['theta'], b['k']) 
                          for b in molspec['angles']]
            else:
                angles = []
            
            cst = MolecularConstraints(name, bonds, angles, [])
            
            self.molecules.append(cst)
        return self
    


class ForceGenerator(object):
    
    def __init__(self, spec):
        self.intermolecular = InterMolecular.from_dict(spec['nonbonded'])
        self.intramolecular = IntraMolecular.from_dict(spec['bonded'])


def to_top(system, potential):
    molecules = [system.subentity(Molecule, i) for i in range(system.dimensions['molecule'])]
    unique_molecules = {}
    [unique_molecules.__setitem__(m.molecule_name, m) for m in molecules]

    # Defaults section
    r = ''.join([comment('Generated by chemlab'),
                 line('[ defaults ]'),
                 comment('nbfunc', 'comb-rule', 'gen-pairs', 'fudgeL', 'fudgeQQ'),
                 line(1, 1, "yes", 0.5, 0.5),
                 line()])
    
    # Non bonded interactions
    r += line('[ atomtypes ]')
    r += comment('name', 'bond_type', 'mass', 'charge', 'ptype', 'C', 'A')
    name_to_type = {}
    
    for atom in potential.intermolecular.particles:
        r += line(atom.name, atom.type, atomic_no(atom.type), atomic_weight(atom.type), 
                  atom.q, 'A', atom.sigma, atom.eps)
        name_to_type[atom.name] = atom.type
    
    r += line()
    r += line('[ nonbondparams ]')
    r += comment('i', 'j', 'func', 'V', 'W')
    # We have to use combination rules...
    pairs_added = set()
    for pair_interaction in potential.intermolecular.pairs:
        pair = name_to_type[pair_interaction.pair[0]], name_to_type[pair_interaction.pair[1]]
        if pair not in pairs_added:
            pairs_added.add(pair)
            r += line(pair[0], 
                      pair[1], 
                      1, 
                      pair_interaction.sigma, 
                      pair_interaction.eps)
    r += line()
    
    for molecule in potential.intramolecular.molecules:
        r += line('[ moleculetype ]')
        r += comment('name', 'nbexcl')
        r += line(molecule.name, 2)
        r += line()
        # Atoms directive...
        r += line('[ atoms ]', just="left")
        r += comment('nr', 'type', 'resnr', 'residue', 'atom', 'cgnr', 'charge', 'mass')
        for i, t in enumerate(unique_molecules[molecule.name].type_array):
            r += line(i + 1, t, 1, molecule.name, t, 1, 0.0)
        #     1  O          1    SOL     OW      1      -0.8476
        r += line()
        
        # Bonds directive...
        if molecule.bonds:
            r += line('[ bonds ]', just="left")
            r += comment('i', 'j', 'funct', 'length', 'force.c.')
            for b in molecule.bonds:
                r += line(b.between[0] + 1, b.between[1] + 1, 1, b.r, b.k)
            r += line()
        
        # Angle directive...
        if molecule.angles:
            r += line('[ angles ]', just="left")
            r += comment('i', 'j', 'k', 'funct', 'angle', 'force.c.')
            for ang in molecule.angles:
                r += line(ang.between[0] + 1,
                          ang.between[1] + 1,
                          ang.between[2] + 1, 1, ang.theta, ang.k)
            r += line()
        
        # Create dihedrals
        for ang in molecule.dihedrals:
            r += line(ang.between[0] + 1,
                      ang.between[1] + 1,
                      ang.between[2] + 1, 1, ang.theta, ang.k)
        r += line()
    
    # System
    r += line('[ system ]')
    counter = 0
    current = -1
    mollist = []
    for t in system.molecule_name:
        if t != current:
            mollist.append((current, counter))
            current = t
            counter = 0
        counter += 1

    mollist.append((current, counter))
    mollist.pop(0)
    
    for mol, counter in mollist:
        r += line(mol, counter)

    return r

def from_top(topfile):
    topfile.read()
    
    # atom_types
    # pair_interactions -> system-wide (they are combined for all molecules)
    # bond_interactions -> relative to each molecule
    # angle_interactions -> relative to each molecule

    # number of molecules -> relative only to the system, but this is a flaw of 
    # the top format, we don't read that
    
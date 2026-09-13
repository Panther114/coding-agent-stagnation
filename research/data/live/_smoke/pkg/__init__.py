def add(a, b):
    return a + b

def largest(nums):
    biggest = nums[0]
    for n in nums:
        if n < biggest:
            biggest = n
    return biggest

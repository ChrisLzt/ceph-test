#!/bin/bash
hosts=/ior/install/bin/hosts #host file 路径
ior=/ior/install/bin/ior #ior 程序路径
M=16 #并发进程数
out_path=/mnt/ikcdir/hpc/
mkdir -p "$out_path"
wrfout_gen() {
    mpirun -f $hosts -np $M $ior -w -s `expr 40960 / $M` -a posix -i 48 -m -k -e -t 1M -b 1M -o $out_path/wrfout$1 > perf_wrfout$1.log
} #wrfout生成一天数据基础函数
wrfrst_gen() {
    [[ ! -z $2 ]] && tail --pid=$2 -f /dev/null; #等待上一个wrfrst文件生成完成
    mpirun -f $hosts -np $M $ior -w -s `expr 4194304 / $M` -a posix -i 1 -m -k -e -t 1M -b 1M -o $out_path/wrfrst$1 > perf_wrfrst$1.log
} #wrfrst生成一天checkpoint数据基础函数
cal_avg() {
    local sum=0
    local count=0
    local log_files=("$@")
    for log in "${log_files[@]}"; do
        mean_bw=$(grep "write" "$log" | tail -n 1 | awk '{print $4}')
        sum=$(echo "$sum + $mean_bw" | bc)
        count=$((count + 1))
    done
    average=$(echo "scale=2; $sum / $count" | bc)
    echo "$average"
}

wrfout_gen 1
echo "wrfout 1 done"
wrfrst_gen 1 &
last_wrfrst_gen_pid=$!
wrfout_gen 2
echo "wrfout 2 done"
wrfrst_gen 2 $last_wrfrst_gen_pid &
last_wrfrst_gen_pid=$!
wrfout_gen 3
echo "wrfout 3 done"
wrfrst_gen 3 $last_wrfrst_gen_pid &
wait

wrfout_log_files=("perf_wrfout1.log" "perf_wrfout2.log" "perf_wrfout3.log")
wrfrst_log_files=("perf_wrfrst1.log" "perf_wrfrst2.log" "perf_wrfrst3.log")
wrfout_bw=$(cal_avg "${wrfout_log_files[@]}")
wrfrst_bw=$(cal_avg "${wrfrst_log_files[@]}")
echo "wrfout Average Mean(MiB) = $wrfout_bw"
echo "wrfrst Average Mean(MiB) = $wrfrst_bw"
